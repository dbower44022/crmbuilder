"""Filtered-tab CHECK->ACT orchestration logic.

Filtered tabs are the YAML representation of EspoCRM's "Report Filter
plus custom scope" pattern, which surfaces a pre-filtered list view as a
top-level entry in the left navigation.

Two artifacts are needed per tab:

1. A Report Filter record (Advanced Pack extension) that defines the
   filter criteria. This *is* writable via REST at ``/api/v1/ReportFilter``.
2. Three metadata files on the EspoCRM server filesystem
   (``scopes/<Scope>.json``, ``clientDefs/<Scope>.json``,
   ``i18n/en_US/Global.json`` patch) that register the scope as a
   navigable tab and bind it to the Report Filter. EspoCRM's
   ``/api/v1/Metadata`` endpoint is GET-only, so these cannot be written
   over REST.

This manager handles part 1 over REST (when Advanced Pack is present)
and emits part 2 as a deploy bundle in the project's reports directory
for the operator to copy onto the server. The bundle lays out files in
the same shape as ``custom/Espo/Custom/Resources/`` so the operator can
``scp -r`` it on top.
"""

from __future__ import annotations

import datetime
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.condition_expression import (
    AllNode,
    AnyNode,
    ConditionNode,
    LeafClause,
)
from espo_impl.core.models import (
    EntityAction,
    EntityDefinition,
    FilteredTab,
    FilteredTabResult,
    FilteredTabStatus,
    ProgramFile,
)
from espo_impl.core.relative_date import (
    is_relative_date,
    resolve_relative_date,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]

_MISSING = object()


class FilteredTabManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class FilteredTabManager:
    """Orchestrates filtered-tab recognition, Report Filter creation, and bundle generation.

    :param client: EspoCRM admin API client.
    :param output_fn: Callback for emitting output messages (message, color).
    :param bundle_root: Optional override for the bundle output root.
        When ``None``, the manager writes to
        ``{project_folder}/reports/filtered_tabs/{run_ts}/``.
    :param run_timestamp: Optional run timestamp (used in the bundle
        directory name). Defaults to the current UTC time.
    """

    def __init__(
        self,
        client: EspoAdminClient,
        output_fn: OutputCallback,
        bundle_root: Path | None = None,
        run_timestamp: datetime.datetime | None = None,
    ) -> None:
        self.client = client
        self.output_fn = output_fn
        self._bundle_root_override = bundle_root
        self._run_ts = run_timestamp or datetime.datetime.now(datetime.UTC)

    def process_filtered_tabs(
        self, program: ProgramFile,
    ) -> list[FilteredTabResult]:
        """Process every filtered tab declared in the program.

        For each tab:

        1. CHECK whether a Report Filter with the same name already
           exists on the target instance for this entity.
        2. CREATE the Report Filter via REST when missing (skipping when
           Advanced Pack is unavailable, marking NOT_SUPPORTED).
        3. Append the tab's three metadata file fragments to an
           in-memory bundle.

        After all tabs are processed, the bundle is written to disk and
        a ``MANUAL CONFIGURATION REQUIRED`` summary line is emitted
        pointing the operator at the bundle directory and the rebuild +
        Tab List steps that must be done in the EspoCRM admin UI.

        :param program: Parsed and validated program file.
        :returns: One result per declared filtered tab.
        """
        results: list[FilteredTabResult] = []
        bundle_entries: list[dict[str, Any]] = []

        # Aggregated language file content (one Global.json for the whole
        # run rather than one per tab) so a single deploy of the bundle
        # registers every label at once.
        scope_names: dict[str, str] = {}

        # Detect Advanced Pack availability lazily, on first tab.
        advanced_pack_state: dict[str, Any] = {"checked": False, "available": True}

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.filtered_tabs:
                continue

            espo_name = get_espo_entity_name(entity_def.name)

            for tab in entity_def.filtered_tabs:
                result = self._process_tab(
                    entity_def, espo_name, tab, advanced_pack_state,
                )
                results.append(result)

                # Always include in the bundle, even when the report
                # filter create failed — the operator can fix the API
                # side and reuse the bundle for the metadata files.
                bundle_entries.append({
                    "entity": entity_def.name,
                    "espo_entity": espo_name,
                    "tab": tab,
                    "result": result,
                })
                scope_names[tab.scope] = tab.label

        if bundle_entries:
            self._write_bundle(bundle_entries, scope_names)

        return results

    # -- per-tab orchestration ------------------------------------------------

    def _process_tab(
        self,
        entity_def: EntityDefinition,
        espo_name: str,
        tab: FilteredTab,
        advanced_pack_state: dict[str, Any],
    ) -> FilteredTabResult:
        """CHECK->ACT for a single filtered tab.

        :param entity_def: Owning entity definition.
        :param espo_name: EspoCRM internal entity name (C-prefixed for custom).
        :param tab: Desired filtered tab from YAML.
        :param advanced_pack_state: Shared dict tracking AP availability.
        :returns: Result for this tab.
        """
        prefix = f"{entity_def.name}.filteredTabs[{tab.id}]"

        if not advanced_pack_state["available"]:
            # We already determined Advanced Pack is missing on a
            # previous tab; skip API and mark NOT_SUPPORTED.
            self.output_fn(
                f"[NOT SUPPORTED] {prefix} — Advanced Pack required for "
                f"Report Filter (bundle still emitted)",
                "yellow",
            )
            return FilteredTabResult(
                entity=entity_def.name,
                tab_id=tab.id,
                scope=tab.scope,
                status=FilteredTabStatus.NOT_SUPPORTED,
                error="Advanced Pack extension not installed",
            )

        # CHECK
        self.output_fn(f"[CHECK]   {prefix} ...", "white")
        status_code, body = self.client.list_report_filters(espo_name)

        if status_code == 401:
            raise FilteredTabManagerError("Authentication failed (HTTP 401)")

        if status_code == 404:
            # Advanced Pack absent — flip the shared flag so subsequent
            # tabs short-circuit, and emit a one-time advisory.
            advanced_pack_state["available"] = False
            advanced_pack_state["checked"] = True
            self.output_fn(
                f"[NOT SUPPORTED] {prefix} — /ReportFilter returned 404; "
                f"Advanced Pack extension is required",
                "yellow",
            )
            return FilteredTabResult(
                entity=entity_def.name,
                tab_id=tab.id,
                scope=tab.scope,
                status=FilteredTabStatus.NOT_SUPPORTED,
                error="Advanced Pack extension not installed",
            )

        if status_code < 0 or status_code >= 400:
            self.output_fn(
                f"[ERROR]   {prefix} list ReportFilter ... HTTP {status_code}",
                "red",
            )
            self.output_fn(f"          {_format_error_detail(body)}", "red")
            return FilteredTabResult(
                entity=entity_def.name,
                tab_id=tab.id,
                scope=tab.scope,
                status=FilteredTabStatus.ERROR,
                error=f"List ReportFilter failed: HTTP {status_code}",
            )

        advanced_pack_state["checked"] = True

        existing_id = self._find_existing_filter_id(body, tab.label)
        if existing_id is not None:
            self.output_fn(
                f"[SKIP]    {prefix} ... ReportFilter '{tab.label}' "
                f"already exists ({existing_id})",
                "gray",
            )
            tab.report_filter_id = existing_id
            return FilteredTabResult(
                entity=entity_def.name,
                tab_id=tab.id,
                scope=tab.scope,
                status=FilteredTabStatus.SKIPPED,
                report_filter_id=existing_id,
            )

        # ACT — create
        try:
            payload = self._build_report_filter_payload(espo_name, tab)
        except ValueError as exc:
            self.output_fn(
                f"[ERROR]   {prefix} ... {exc}", "red",
            )
            return FilteredTabResult(
                entity=entity_def.name,
                tab_id=tab.id,
                scope=tab.scope,
                status=FilteredTabStatus.ERROR,
                error=str(exc),
            )

        self.output_fn(f"[CREATE]  {prefix} ReportFilter ...", "white")
        status_code, body = self.client.create_report_filter(payload)

        if status_code == 401:
            raise FilteredTabManagerError("Authentication failed (HTTP 401)")

        if status_code < 0 or status_code >= 400:
            self.output_fn(
                f"[ERROR]   {prefix} create ReportFilter ... "
                f"HTTP {status_code}",
                "red",
            )
            self.output_fn(f"          {_format_error_detail(body)}", "red")
            return FilteredTabResult(
                entity=entity_def.name,
                tab_id=tab.id,
                scope=tab.scope,
                status=FilteredTabStatus.ERROR,
                error=f"Create ReportFilter failed: HTTP {status_code}",
            )

        new_id = (body or {}).get("id") if isinstance(body, dict) else None
        if not new_id:
            self.output_fn(
                f"[ERROR]   {prefix} create ReportFilter ... no id in response",
                "red",
            )
            return FilteredTabResult(
                entity=entity_def.name,
                tab_id=tab.id,
                scope=tab.scope,
                status=FilteredTabStatus.ERROR,
                error="Create ReportFilter returned no id",
            )

        tab.report_filter_id = str(new_id)
        self.output_fn(
            f"[CREATE]  {prefix} ReportFilter ... OK ({new_id})", "green",
        )
        return FilteredTabResult(
            entity=entity_def.name,
            tab_id=tab.id,
            scope=tab.scope,
            status=FilteredTabStatus.CREATED,
            report_filter_id=str(new_id),
        )

    @staticmethod
    def _find_existing_filter_id(
        body: Any, name: str,
    ) -> str | None:
        """Look up an existing Report Filter by name in a list response.

        :param body: List response body from ``list_report_filters``.
        :param name: Desired filter name (matches the YAML ``label``).
        :returns: Matching filter id, or None.
        """
        if not isinstance(body, dict):
            return None
        items = body.get("list")
        if not isinstance(items, list):
            return None
        for item in items:
            if isinstance(item, dict) and item.get("name") == name:
                fid = item.get("id")
                return str(fid) if fid else None
        return None

    # -- payload + where-item construction ------------------------------------

    def _build_report_filter_payload(
        self, espo_name: str, tab: FilteredTab,
    ) -> dict[str, Any]:
        """Build the POST /ReportFilter payload for a tab.

        :param espo_name: EspoCRM internal entity name.
        :param tab: Filtered-tab spec (must have ``filter`` parsed).
        :returns: Payload dict.
        :raises ValueError: If the parsed filter is missing.
        """
        if tab.filter is None:
            raise ValueError("filter AST is missing — validation should have caught this")
        where = self._to_where_items(tab.filter)
        return {
            "name": tab.label,
            "entityType": espo_name,
            "data": {"where": where},
        }

    def _to_where_items(self, node: ConditionNode) -> list[dict[str, Any]]:
        """Convert a condition AST root to a list of EspoCRM where-items.

        EspoCRM where-items use ``{type, attribute, value}`` rather than
        the YAML AST's ``{field, op, value}``, and combine groups via
        ``{type: "and"|"or", value: [...]}``. Two semantic conversions
        also happen here:

        - The literal string ``"$user"`` becomes a where-type
          ``currentUser`` clause (no ``value`` needed).
        - Relative-date tokens (Section 11) are resolved to absolute
          ``YYYY-MM-DD`` strings using the current process date.

        :param node: Root of the parsed condition AST.
        :returns: A list of where-items (always a list, since EspoCRM's
            top-level ``data.where`` is a list of group/leaf items).
        """
        item = self._node_to_where(node)
        # Top-level form must be a list. Wrap a single leaf in an
        # implicit "and" group so EspoCRM treats it consistently with
        # multi-clause filters.
        if isinstance(item, list):
            return item
        return [item]

    def _node_to_where(self, node: ConditionNode) -> dict[str, Any] | list[dict[str, Any]]:
        """Recursively convert a single AST node to a where-item or list."""
        if isinstance(node, AllNode):
            return {
                "type": "and",
                "value": [self._node_to_where(c) for c in node.children],
            }
        if isinstance(node, AnyNode):
            return {
                "type": "or",
                "value": [self._node_to_where(c) for c in node.children],
            }
        if isinstance(node, LeafClause):
            return self._leaf_to_where(node)
        raise TypeError(f"Unexpected node type: {type(node)}")  # pragma: no cover

    def _leaf_to_where(self, leaf: LeafClause) -> dict[str, Any]:
        """Convert a leaf clause to a single EspoCRM where-item."""
        # $user sentinel becomes EspoCRM's currentUser where-type.
        value = getattr(leaf, "value", _MISSING)
        if leaf.op == "equals" and value == "$user":
            return {"type": "currentUser", "attribute": leaf.field}
        if leaf.op == "notEquals" and value == "$user":
            return {"type": "notCurrentUser", "attribute": leaf.field}

        item: dict[str, Any] = {"type": leaf.op, "attribute": leaf.field}

        if leaf.op in ("isNull", "isNotNull"):
            return item

        if value is _MISSING:
            return item

        # Resolve relative-date tokens to absolute dates, including
        # element-wise resolution inside list values for in/notIn.
        if isinstance(value, str) and is_relative_date(value):
            item["value"] = resolve_relative_date(value)
        elif isinstance(value, list):
            item["value"] = [
                resolve_relative_date(v)
                if isinstance(v, str) and is_relative_date(v)
                else v
                for v in value
            ]
        else:
            item["value"] = value

        return item

    # -- bundle generation ----------------------------------------------------

    def _bundle_root(self) -> Path:
        """Resolve the bundle root directory."""
        if self._bundle_root_override is not None:
            return self._bundle_root_override
        reports = self.client.profile.reports_dir
        if reports is None:
            # Fallback when no project_folder is configured — write next
            # to the cwd. The operator will see the path in the log.
            reports = Path.cwd() / "reports"
        ts = self._run_ts.strftime("%Y%m%dT%H%M%SZ")
        return reports / "filtered_tabs" / ts

    def _write_bundle(
        self,
        entries: list[dict[str, Any]],
        scope_names: dict[str, str],
    ) -> None:
        """Write the deploy bundle for all processed tabs.

        Bundle layout (mirrors ``custom/Espo/Custom/Resources/`` so the
        operator can scp it on top)::

            {bundle_root}/
            ├── README.txt
            ├── manifest.json
            ├── scopes/
            │   └── <Scope>.json
            ├── clientDefs/
            │   └── <Scope>.json
            └── i18n/
                └── en_US/
                    └── Global.json

        :param entries: Per-tab work items collected during the run.
        :param scope_names: Aggregated label map for Global.json.
        """
        root = self._bundle_root()
        try:
            root.mkdir(parents=True, exist_ok=True)
            (root / "scopes").mkdir(exist_ok=True)
            (root / "clientDefs").mkdir(exist_ok=True)
            (root / "i18n" / "en_US").mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.output_fn(
                f"[ERROR]   filteredTabs bundle ... cannot create "
                f"directory {root}: {exc}",
                "red",
            )
            return

        manifest: list[dict[str, Any]] = []

        for entry in entries:
            tab: FilteredTab = entry["tab"]
            espo_entity: str = entry["espo_entity"]
            result: FilteredTabResult = entry["result"]

            scope_path = root / "scopes" / f"{tab.scope}.json"
            client_def_path = root / "clientDefs" / f"{tab.scope}.json"

            scope_path.write_text(
                json.dumps(self._scope_definition(tab), indent=2) + "\n",
                encoding="utf-8",
            )
            client_def_path.write_text(
                json.dumps(
                    self._client_def(espo_entity, tab.report_filter_id),
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            manifest.append({
                "entity": entry["entity"],
                "espoEntity": espo_entity,
                "tabId": tab.id,
                "scope": tab.scope,
                "label": tab.label,
                "navOrder": tab.nav_order,
                "reportFilterId": tab.report_filter_id,
                "status": result.status.value,
                "scopeFile": str(scope_path.relative_to(root)),
                "clientDefFile": str(client_def_path.relative_to(root)),
            })

        global_path = root / "i18n" / "en_US" / "Global.json"
        global_path.write_text(
            json.dumps({"scopeNames": scope_names}, indent=2) + "\n",
            encoding="utf-8",
        )

        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "generatedAt": self._run_ts.isoformat(),
                    "tabs": manifest,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        readme_path = root / "README.txt"
        readme_path.write_text(
            self._readme_text(manifest), encoding="utf-8",
        )

        self.output_fn(
            f"[BUNDLE]  filteredTabs ... wrote {len(entries)} tab(s) to {root}",
            "green",
        )
        self.output_fn(
            f"[MANUAL]  Copy {root} contents into "
            f"custom/Espo/Custom/Resources/ on the server, then "
            f"Admin → Rebuild and add the labels to the Tab List.",
            "yellow",
        )

    @staticmethod
    def _scope_definition(tab: FilteredTab) -> dict[str, Any]:
        """Build the scopes/<Scope>.json content for a tab."""
        return {
            "entity": False,
            "tab": True,
            "acl": tab.acl,
            "disabled": False,
            "module": "Custom",
            "isCustom": True,
        }

    @staticmethod
    def _client_def(
        espo_entity: str, report_filter_id: str | None,
    ) -> dict[str, Any]:
        """Build the clientDefs/<Scope>.json content for a tab.

        When the Report Filter id is unknown (Advanced Pack absent or
        create failed), the ``defaultFilter`` value is left as a clearly
        marked placeholder the operator must replace before rebuilding.
        """
        default_filter = (
            f"reportFilter{report_filter_id}"
            if report_filter_id
            else "REPLACE_WITH_reportFilter<id>"
        )
        return {
            "controller": "record",
            "entity": espo_entity,
            "defaultFilter": default_filter,
        }

    def _readme_text(self, manifest: list[dict[str, Any]]) -> str:
        """Render the human-readable install instructions."""
        lines = [
            "Filtered-tab deploy bundle",
            "==========================",
            "",
            f"Generated at: {self._run_ts.isoformat()}",
            f"Tab count:    {len(manifest)}",
            "",
            "Install steps",
            "-------------",
            "1. Copy this bundle's contents on top of the EspoCRM server's",
            "   custom/Espo/Custom/Resources/ directory. From a workstation",
            "   that can reach the server:",
            "",
            "       scp -r ./* root@<host>:/var/www/espocrm/data/"
            "custom/Espo/Custom/Resources/",
            "",
            "   (Adjust the destination path for your install layout.)",
            "",
            "2. In the EspoCRM admin UI: Administration → Rebuild.",
            "",
            "3. Administration → User Interface → Tab List. Add the new",
            "   labels (listed below) and drag them into the desired order.",
            "",
            "4. Save and hard-refresh the browser.",
            "",
            "Tabs in this bundle",
            "-------------------",
        ]
        for entry in manifest:
            order = (
                f" (navOrder: {entry['navOrder']})"
                if entry.get("navOrder") is not None
                else ""
            )
            rf_id = entry.get("reportFilterId")
            rf_note = (
                f"reportFilter id: {rf_id}"
                if rf_id
                else "ReportFilter NOT created (see status)"
            )
            lines.append(
                f"- {entry['scope']} → \"{entry['label']}\" "
                f"on {entry['espoEntity']}{order}; status: "
                f"{entry['status']}; {rf_note}"
            )
        lines.append("")
        lines.append(
            "If a tab's status is 'not_supported' or 'error', the bundle"
        )
        lines.append(
            "still includes its scope/clientDef files; replace any"
        )
        lines.append(
            "REPLACE_WITH_reportFilter<id> placeholder before rebuilding."
        )
        lines.append("")
        return "\n".join(lines)
