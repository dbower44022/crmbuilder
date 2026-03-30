"""CRM Platform Comparison window.

Standalone window for browsing, comparing, and analyzing CRM platform
API capabilities against the CRM Builder feature set.
"""

import logging
from pathlib import Path

import yaml
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# ─── Rating Colors ─────────────────────────────────────────────────────
# Mirrors output_panel.py COLOR_MAP pattern.

RATING_COLORS: dict[str, str] = {
    "full": "#4CAF50",
    "partial": "#FFC107",
    "indirect": "#FF9800",
    "read_only": "#FF9800",
    "none": "#F44336",
    "unknown": "#9E9E9E",
    "na": "#9E9E9E",
}

RATING_SYMBOLS: dict[str, str] = {
    "full": "Full",
    "partial": "Partial",
    "read_only": "Read-only",
    "indirect": "Indirect",
    "none": "None",
    "na": "N/A",
    "unknown": "\u2014",
    "true": "Yes",
    "false": "No",
    "True": "Yes",
    "False": "No",
}

# ─── Capability checks for gaps analysis ───────────────────────────────

GAP_CHECKS: list[tuple[str, str, str]] = [
    ("Entity Creation", "entity_management", "create_entity"),
    ("Entity Deletion", "entity_management", "delete_entity"),
    ("Entity Existence Check", "entity_management", "check_existence"),
    ("Cache Rebuild", "entity_management", "cache_rebuild"),
    ("Field Creation", "field_management", "create_field"),
    ("Field Update", "field_management", "update_field"),
    ("Field Metadata Read", "field_management", "read_metadata"),
    ("Layout Read", "layout_management", "read_layouts"),
    ("Layout Write", "layout_management", "write_layouts"),
    ("Detail View", "layout_management", "detail_view"),
    ("Edit View", "layout_management", "edit_view"),
    ("List View", "layout_management", "list_view"),
    ("Panels", "layout_management", "panels"),
    ("Tabs", "layout_management", "tabs"),
    ("Conditional Visibility", "layout_management", "conditional_visibility"),
    ("Relationship Creation", "relationship_management", "create_relationship"),
    ("One-to-Many", "relationship_management", "one_to_many"),
    ("Many-to-Many", "relationship_management", "many_to_many"),
    ("Link Labels", "relationship_management", "link_labels"),
    ("Audit Both Sides", "relationship_management", "audit_both_sides"),
    ("Multiple List Views", "layout_management", "multiple_list_views"),
    ("Record Create", "data_operations", "create_record"),
    ("Record Update", "data_operations", "update_record"),
    ("Search by Email", "data_operations", "search_by_email"),
]

# ─── Compare table sections ────────────────────────────────────────────

COMPARE_SECTIONS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("Entity Management", [
        ("Create Entity", "entity_management", "create_entity"),
        ("Delete Entity", "entity_management", "delete_entity"),
        ("Check Existence", "entity_management", "check_existence"),
        ("Cache Rebuild", "entity_management", "cache_rebuild"),
    ]),
    ("Field Management", [
        ("Create Field", "field_management", "create_field"),
        ("Update Field", "field_management", "update_field"),
        ("Read Metadata", "field_management", "read_metadata"),
    ]),
    ("Layout Management", [
        ("Read Layouts", "layout_management", "read_layouts"),
        ("Write Layouts", "layout_management", "write_layouts"),
        ("Detail View", "layout_management", "detail_view"),
        ("Edit View", "layout_management", "edit_view"),
        ("List View", "layout_management", "list_view"),
        ("Panels/Sections", "layout_management", "panels"),
        ("Tabs", "layout_management", "tabs"),
        ("Conditional Visibility", "layout_management", "conditional_visibility"),
        ("Multiple List Views", "layout_management", "multiple_list_views"),
    ]),
    ("Relationship Management", [
        ("Create Relationship", "relationship_management", "create_relationship"),
        ("One-to-Many", "relationship_management", "one_to_many"),
        ("Many-to-Many", "relationship_management", "many_to_many"),
        ("Link Labels", "relationship_management", "link_labels"),
        ("Cascade Delete", "relationship_management", "cascade_delete"),
    ]),
    ("Data Operations", [
        ("Create Record", "data_operations", "create_record"),
        ("Search by Email", "data_operations", "search_by_email"),
        ("Upsert", "data_operations", "upsert"),
        ("Batch Create", "data_operations", "batch_create"),
    ]),
    ("Workflow & Automation", [
        ("Create Rules", "workflow_automation", "create_rules"),
        ("Create Flows", "workflow_automation", "create_flows"),
        ("Approval Processes", "workflow_automation", "approval_processes"),
    ]),
    ("Roles & Permissions", [
        ("Create Roles", "roles_permissions", "create_roles"),
        ("Field-Level Security", "roles_permissions", "field_level_security"),
    ]),
    ("Other", [
        ("Dashboards", "dashboards_reports", "create_dashboards"),
        ("Email Templates", "email_templates", "crud_templates"),
        ("Webhooks", "webhooks_events", "outbound_webhooks"),
    ]),
]


# ─── Data helpers (pure functions, no side effects) ────────────────────

def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_platforms(platforms_dir: Path) -> list[dict]:
    platforms = []
    for path in sorted(platforms_dir.glob("*.yaml")):
        try:
            data = _load_yaml(path)
        except Exception:
            logger.warning("Skipping %s: failed to parse YAML", path.name)
            continue
        if not isinstance(data, dict):
            logger.warning("Skipping %s: not a valid YAML mapping", path.name)
            continue
        data["_path"] = str(path)
        platforms.append(data)
    return sorted(platforms, key=lambda p: p.get("name", ""))


def _get_rating(platform: dict, *keys: str) -> str:
    node = platform
    for key in keys:
        if isinstance(node, dict):
            node = node.get(key)
        else:
            return "unknown"
    if node is None:
        return "unknown"
    if isinstance(node, dict):
        return node.get("rating", node.get("supported", "unknown"))
    if isinstance(node, bool):
        return "full" if node else "none"
    return str(node)


def _rating_text(rating: str) -> str:
    return RATING_SYMBOLS.get(str(rating), str(rating))


def _calculate_tier(platform: dict) -> tuple[int, str]:
    ec = _get_rating(platform, "entity_management", "create_entity")
    fc = _get_rating(platform, "field_management", "create_field")
    lw = _get_rating(platform, "layout_management", "write_layouts")
    rc = _get_rating(platform, "relationship_management", "create_relationship")
    if all(r == "full" for r in [ec, fc, lw, rc]):
        return 1, "Full Feature Coverage"
    if fc in ("full", "partial") and (
        ec in ("full", "partial", "indirect")
        or rc in ("full", "partial")
    ):
        return 2, "Strong but Gaps"
    if fc in ("full", "partial"):
        return 3, "Fields Only"
    return 4, "Data API Only"


def _format_price(platform: dict) -> str:
    pricing = platform.get("pricing", {})
    free = pricing.get("free_tier", "None")
    min_paid = pricing.get("min_paid_per_user_month")
    admin_api = pricing.get("full_admin_api_per_user_month")
    parts = []
    if free and free != "None":
        parts.append(f"Free: {free}")
    if min_paid is not None:
        parts.append(f"Min: ${min_paid}/user/mo")
    if admin_api is not None and isinstance(admin_api, (int, float)) and admin_api != min_paid:
        parts.append(f"Admin API: ${admin_api}/user/mo")
    return " | ".join(parts) if parts else "N/A"


# ─── Window ────────────────────────────────────────────────────────────

class CrmCompareWindow(QMainWindow):
    """Standalone window for CRM platform comparison and analysis.

    :param base_dir: Project root directory.
    :param parent: Parent widget.
    """

    def __init__(self, base_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._base_dir = base_dir
        self._platforms_dir = base_dir / "docs" / "crm-platforms" / "platforms"
        self._platforms: list[dict] = []
        self._load_data()
        self._build_ui()

    def _load_data(self) -> None:
        """Load all platform YAML files."""
        try:
            self._platforms = _load_platforms(self._platforms_dir)
        except Exception:
            logger.exception("Failed to load CRM platform data")
            self._platforms = []

    def _build_ui(self) -> None:
        """Build the main window layout."""
        self.setWindowTitle("CRM Platform Comparison")
        self.setMinimumSize(1100, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        if not self._platforms:
            error_label = QLabel(
                "No platform data found.\n\n"
                f"Expected YAML files in:\n{self._platforms_dir}"
            )
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("color: #F44336; font-size: 14px;")
            layout.addWidget(error_label)
            return

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_platforms_tab(), "Platforms")
        self._tabs.addTab(self._build_compare_tab(), "Compare")
        self._tabs.addTab(self._build_tiers_tab(), "Tiers")
        self._tabs.addTab(self._build_gaps_tab(), "Gaps")
        self._tabs.addTab(self._build_pricing_tab(), "Pricing")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

    def _on_tab_changed(self, index: int) -> None:
        """Refresh compare tab when switching to it."""
        if index == 1:
            self._refresh_compare_tab()

    # ─── Shared helpers ────────────────────────────────────────────

    def _rating_label(self, rating: str) -> QLabel:
        """Create a color-coded label for a rating value.

        :param rating: Rating string.
        :returns: Styled QLabel.
        """
        text = _rating_text(rating)
        color = RATING_COLORS.get(rating, "#9E9E9E")
        label = QLabel(text)
        label.setStyleSheet(f"color: {color}; font-weight: bold;")
        return label

    def _rating_badge(self, rating: str) -> QLabel:
        """Create a badge-style label for a rating.

        :param rating: Rating string.
        :returns: Styled QLabel with background.
        """
        text = _rating_text(rating)
        bg = RATING_COLORS.get(rating, "#9E9E9E")
        label = QLabel(f"  {text}  ")
        label.setStyleSheet(
            f"background-color: {bg}; color: white; font-weight: bold; "
            f"padding: 2px 8px; border-radius: 3px;"
        )
        return label

    def _tier_badge(self, tier_num: int, tier_label: str) -> QLabel:
        """Create a badge for a tier number.

        :param tier_num: Tier number (1-4).
        :param tier_label: Tier label.
        :returns: Styled QLabel.
        """
        colors = {1: "#4CAF50", 2: "#FFC107", 3: "#FF9800", 4: "#F44336"}
        bg = colors.get(tier_num, "#9E9E9E")
        label = QLabel(f"  Tier {tier_num}: {tier_label}  ")
        label.setStyleSheet(
            f"background-color: {bg}; color: white; font-weight: bold; "
            f"padding: 3px 10px; border-radius: 4px;"
        )
        return label

    @staticmethod
    def _make_scroll_area(widget: QWidget) -> QScrollArea:
        """Wrap a widget in a scroll area.

        :param widget: Widget to wrap.
        :returns: QScrollArea containing the widget.
        """
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll

    # ─── Platforms tab ─────────────────────────────────────────────

    def _build_platforms_tab(self) -> QWidget:
        """Build the platforms browse tab with list and detail panel."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left column: platform list + comparison checkboxes
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # Browse list
        browse_group = QGroupBox("Platforms")
        browse_layout = QVBoxLayout()
        self._platform_list = QListWidget()
        for p in self._platforms:
            tier_num, _ = _calculate_tier(p)
            self._platform_list.addItem(f"{p['name']}  (Tier {tier_num})")
        self._platform_list.currentRowChanged.connect(self._on_platform_selected)
        browse_layout.addWidget(self._platform_list)
        browse_group.setLayout(browse_layout)
        left_layout.addWidget(browse_group)

        # Comparison selection
        compare_group = QGroupBox("Select for Comparison")
        compare_layout = QVBoxLayout()
        self._compare_list = QListWidget()
        for p in self._platforms:
            item = QListWidgetItem(p["name"])
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            self._compare_list.addItem(item)
        compare_layout.addWidget(self._compare_list)

        select_row = QHBoxLayout()
        select_all_btn = QPushButton("All Tier 1")
        select_all_btn.clicked.connect(self._on_select_tier1)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear_selection)
        select_row.addWidget(select_all_btn)
        select_row.addWidget(clear_btn)
        compare_layout.addLayout(select_row)

        compare_group.setLayout(compare_layout)
        left_layout.addWidget(compare_group)

        splitter.addWidget(left)

        # Right column: detail panel
        self._detail_stack = QStackedWidget()
        placeholder = QLabel("Select a platform to view details")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: gray; font-size: 13px;")
        self._detail_stack.addWidget(placeholder)
        splitter.addWidget(self._detail_stack)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)
        return tab

    def _on_platform_selected(self, row: int) -> None:
        """Show detail panel for the selected platform."""
        if row < 0 or row >= len(self._platforms):
            self._detail_stack.setCurrentIndex(0)
            return

        platform = self._platforms[row]
        detail = self._build_platform_detail(platform)

        # Replace old detail widget if it exists
        while self._detail_stack.count() > 1:
            old = self._detail_stack.widget(1)
            self._detail_stack.removeWidget(old)
            old.deleteLater()

        self._detail_stack.addWidget(detail)
        self._detail_stack.setCurrentIndex(1)

    def _on_select_tier1(self) -> None:
        """Check all Tier 1 platforms in the comparison list."""
        for i in range(self._compare_list.count()):
            item = self._compare_list.item(i)
            platform = self._platforms[i]
            tier_num, _ = _calculate_tier(platform)
            item.setCheckState(
                Qt.CheckState.Checked if tier_num == 1
                else Qt.CheckState.Unchecked
            )

    def _on_clear_selection(self) -> None:
        """Uncheck all platforms in the comparison list."""
        for i in range(self._compare_list.count()):
            self._compare_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _get_selected_slugs(self) -> list[str]:
        """Return slugs of checked platforms."""
        slugs = []
        for i in range(self._compare_list.count()):
            if self._compare_list.item(i).checkState() == Qt.CheckState.Checked:
                slugs.append(self._platforms[i].get("slug", ""))
        return slugs

    def _build_platform_detail(self, platform: dict) -> QScrollArea:
        """Build the full detail view for a platform.

        :param platform: Platform data dict.
        :returns: Scroll area containing the detail panel.
        """
        content = QWidget()
        layout = QVBoxLayout(content)

        # Header
        layout.addWidget(self._make_header_section(platform))

        # Scorecard (the 4 tier-determining capabilities)
        layout.addWidget(self._make_scorecard_section(platform))

        # Capability sections
        for section_name, rows in COMPARE_SECTIONS:
            layout.addWidget(self._make_capability_group(
                section_name, platform, rows
            ))

        layout.addStretch()
        return self._make_scroll_area(content)

    def _make_header_section(self, platform: dict) -> QGroupBox:
        """Build the header section with name, type, tier, pricing."""
        group = QGroupBox()
        layout = QVBoxLayout()

        # Name + type
        name_label = QLabel(platform.get("name", "Unknown"))
        name_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(name_label)

        type_label = QLabel(
            f"{platform.get('type', '')} \u2014 {platform.get('deployment', '')}"
        )
        type_label.setStyleSheet("color: gray;")
        layout.addWidget(type_label)

        # Open source + license
        oss = platform.get("open_source", False)
        lic = platform.get("license", "")
        if oss:
            oss_label = QLabel(f"\u2713  Open Source ({lic})")
            oss_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            oss_label = QLabel("Proprietary" + (f" ({lic})" if lic and lic != "Proprietary" else ""))
            oss_label.setStyleSheet("color: gray;")
        layout.addWidget(oss_label)

        # Tier badge
        tier_num, tier_label = _calculate_tier(platform)
        tier_row = QHBoxLayout()
        tier_row.addWidget(self._tier_badge(tier_num, tier_label))
        tier_row.addStretch()
        layout.addLayout(tier_row)

        # API info
        api = platform.get("api", {})
        protocol = ", ".join(api.get("protocol", []))
        auth = ", ".join(api.get("auth_methods", []))
        if protocol:
            layout.addWidget(QLabel(f"API: {protocol}"))
        if auth:
            layout.addWidget(QLabel(f"Auth: {auth}"))

        rate = api.get("rate_limit", "")
        if rate:
            layout.addWidget(QLabel(f"Rate Limit: {rate}"))

        # Pricing
        price_text = _format_price(platform)
        if price_text != "N/A":
            layout.addWidget(QLabel(f"Pricing: {price_text}"))

        reviewed = platform.get("last_reviewed", "")
        if reviewed:
            layout.addWidget(QLabel(
                f"Last Reviewed: {reviewed}"
            ))

        group.setLayout(layout)
        return group

    def _make_scorecard_section(self, platform: dict) -> QGroupBox:
        """Build the scorecard showing the 4 tier-determining ratings."""
        group = QGroupBox("Scorecard (Tier Criteria)")
        layout = QVBoxLayout()

        criteria = [
            ("Entity Creation", "entity_management", "create_entity"),
            ("Field Creation", "field_management", "create_field"),
            ("Layout Write", "layout_management", "write_layouts"),
            ("Relationship Creation", "relationship_management", "create_relationship"),
        ]

        for label, *keys in criteria:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addStretch()
            rating = _get_rating(platform, *keys)
            row.addWidget(self._rating_badge(rating))
            layout.addLayout(row)

        group.setLayout(layout)
        return group

    def _make_capability_group(
        self, title: str, platform: dict,
        rows: list[tuple[str, str, str]],
    ) -> QGroupBox:
        """Build a collapsible capability group with rated rows.

        :param title: Section title.
        :param platform: Platform data dict.
        :param rows: List of (label, key1, key2) tuples.
        :returns: QGroupBox with capability ratings.
        """
        group = QGroupBox(title)
        layout = QVBoxLayout()

        for label, *keys in rows:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addStretch()
            rating = _get_rating(platform, *keys)
            row.addWidget(self._rating_label(rating))

            # Show method/notes if available
            node = platform
            for key in keys:
                if isinstance(node, dict):
                    node = node.get(key)
                else:
                    node = None
                    break
            if isinstance(node, dict):
                method = node.get("method", node.get("notes", ""))
                if method:
                    notes_label = QLabel(method)
                    notes_label.setStyleSheet("color: gray; font-size: 11px;")
                    notes_label.setWordWrap(True)
                    layout.addLayout(row)
                    layout.addWidget(notes_label)
                    continue
            layout.addLayout(row)

        group.setLayout(layout)
        return group

    # ─── Compare tab ───────────────────────────────────────────────

    def _build_compare_tab(self) -> QWidget:
        """Build the comparison tab with a lazy-loaded table."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._compare_stack = QStackedWidget()

        # Index 0: placeholder
        placeholder = QLabel(
            "Select platforms in the Platforms tab, then switch here.\n\n"
            "Use the checkboxes under \u201cSelect for Comparison\u201d "
            "to pick 2\u20136 platforms."
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: gray; font-size: 13px;")
        self._compare_stack.addWidget(placeholder)

        layout.addWidget(self._compare_stack)
        return tab

    def _refresh_compare_tab(self) -> None:
        """Rebuild the comparison table from current checkbox state."""
        slugs = self._get_selected_slugs()
        if not slugs:
            self._compare_stack.setCurrentIndex(0)
            return

        platforms = [p for p in self._platforms if p.get("slug") in slugs]
        table = self._build_compare_table(platforms)

        # Replace old table if present
        while self._compare_stack.count() > 1:
            old = self._compare_stack.widget(1)
            self._compare_stack.removeWidget(old)
            old.deleteLater()

        self._compare_stack.addWidget(table)
        self._compare_stack.setCurrentIndex(1)

    def _build_compare_table(self, platforms: list[dict]) -> QTableWidget:
        """Build the head-to-head comparison table.

        :param platforms: List of platform dicts to compare.
        :returns: Populated QTableWidget.
        """
        # Count total rows (section headers + data rows)
        total_rows = 0
        for _section_name, rows in COMPARE_SECTIONS:
            total_rows += 1 + len(rows)

        n_cols = 1 + len(platforms)
        table = QTableWidget(total_rows, n_cols)
        table.setHorizontalHeaderLabels(
            ["Capability"] + [p.get("name", "?") for p in platforms]
        )
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        for col in range(1, n_cols):
            table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.Stretch
            )

        row_idx = 0
        section_font = QFont()
        section_font.setBold(True)

        for section_name, rows in COMPARE_SECTIONS:
            # Section header row
            header_item = QTableWidgetItem(section_name)
            header_item.setFont(section_font)
            header_item.setBackground(QColor("#2a2a2a"))
            header_item.setForeground(QColor("#D4D4D4"))
            table.setItem(row_idx, 0, header_item)
            for col in range(1, n_cols):
                filler = QTableWidgetItem("")
                filler.setBackground(QColor("#2a2a2a"))
                table.setItem(row_idx, col, filler)
            table.setSpan(row_idx, 0, 1, n_cols)
            row_idx += 1

            # Data rows
            for label, *keys in rows:
                table.setItem(row_idx, 0, QTableWidgetItem(label))
                for col, p in enumerate(platforms, start=1):
                    rating = _get_rating(p, *keys)
                    text = _rating_text(rating)
                    item = QTableWidgetItem(text)
                    color = RATING_COLORS.get(rating, "#9E9E9E")
                    item.setForeground(QColor(color))
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )
                    table.setItem(row_idx, col, item)
                row_idx += 1

        return table

    # ─── Tiers tab ─────────────────────────────────────────────────

    def _build_tiers_tab(self) -> QScrollArea:
        """Build the tier assessment tab."""
        content = QWidget()
        layout = QVBoxLayout(content)

        # Group platforms by tier
        tiers: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: []}
        for p in self._platforms:
            tier_num, _ = _calculate_tier(p)
            tiers[tier_num].append(p)

        tier_descriptions = {
            1: "Entity, field, layout, and relationship CRUD all via API",
            2: "Most capabilities via API; missing layout or entity creation",
            3: "Custom field creation via API; no entity/layout/relationship",
            4: "Record CRUD only; no schema/metadata management",
        }

        for tier_num in sorted(tiers.keys()):
            plats = tiers[tier_num]
            desc = tier_descriptions[tier_num]
            group = QGroupBox(f"Tier {tier_num} \u2014 {desc}")
            group_layout = QVBoxLayout()

            if not plats:
                group_layout.addWidget(QLabel("(none)"))
            else:
                for p in sorted(plats, key=lambda x: x.get("name", "")):
                    row = QHBoxLayout()

                    name_lbl = QLabel(p.get("name", "?"))
                    name_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
                    row.addWidget(name_lbl)

                    type_lbl = QLabel(p.get("type", ""))
                    type_lbl.setStyleSheet("color: gray;")
                    row.addWidget(type_lbl)

                    row.addStretch()

                    # Show the 4 criteria as small badges
                    criteria = [
                        ("E", "entity_management", "create_entity"),
                        ("F", "field_management", "create_field"),
                        ("L", "layout_management", "write_layouts"),
                        ("R", "relationship_management", "create_relationship"),
                    ]
                    for abbrev, *keys in criteria:
                        rating = _get_rating(p, *keys)
                        color = RATING_COLORS.get(rating, "#9E9E9E")
                        badge = QLabel(f" {abbrev} ")
                        badge.setToolTip(
                            f"{abbrev}: {_rating_text(rating)}"
                        )
                        badge.setStyleSheet(
                            f"background-color: {color}; color: white; "
                            f"font-weight: bold; padding: 1px 4px; "
                            f"border-radius: 2px; font-size: 11px;"
                        )
                        row.addWidget(badge)

                    row.addSpacing(10)

                    price_lbl = QLabel(_format_price(p))
                    price_lbl.setStyleSheet("color: gray; font-size: 11px;")
                    row.addWidget(price_lbl)

                    group_layout.addLayout(row)

            group.setLayout(group_layout)
            layout.addWidget(group)

        # Legend
        legend_group = QGroupBox("Legend")
        legend_layout = QHBoxLayout()
        legend_items = [
            ("E", "Entity Creation"),
            ("F", "Field Creation"),
            ("L", "Layout Write"),
            ("R", "Relationship Creation"),
        ]
        for abbrev, desc in legend_items:
            legend_layout.addWidget(QLabel(f"{abbrev} = {desc}"))
        legend_layout.addStretch()
        legend_group.setLayout(legend_layout)
        layout.addWidget(legend_group)

        layout.addStretch()
        return self._make_scroll_area(content)

    # ─── Gaps tab ──────────────────────────────────────────────────

    def _build_gaps_tab(self) -> QWidget:
        """Build the gap analysis tab with platform selector."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Platform selector
        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Platform:"))
        self._gaps_combo = QComboBox()
        for p in self._platforms:
            self._gaps_combo.addItem(p.get("name", "?"))
        self._gaps_combo.currentIndexChanged.connect(
            self._on_gaps_platform_changed
        )
        selector_row.addWidget(self._gaps_combo)
        selector_row.addStretch()
        layout.addLayout(selector_row)

        # Content area
        self._gaps_stack = QStackedWidget()
        placeholder = QLabel("Select a platform above")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: gray;")
        self._gaps_stack.addWidget(placeholder)
        layout.addWidget(self._gaps_stack)

        # Trigger initial selection
        if self._platforms:
            self._on_gaps_platform_changed(0)

        return tab

    def _on_gaps_platform_changed(self, index: int) -> None:
        """Rebuild gaps content when platform selection changes."""
        if index < 0 or index >= len(self._platforms):
            return

        platform = self._platforms[index]
        content = self._build_gaps_content(platform)

        while self._gaps_stack.count() > 1:
            old = self._gaps_stack.widget(1)
            self._gaps_stack.removeWidget(old)
            old.deleteLater()

        self._gaps_stack.addWidget(content)
        self._gaps_stack.setCurrentIndex(1)

    def _build_gaps_content(self, platform: dict) -> QScrollArea:
        """Build the gaps analysis content for a platform.

        :param platform: Platform data dict.
        :returns: Scroll area with gap analysis.
        """
        content = QWidget()
        layout = QVBoxLayout(content)

        # Header with tier
        tier_num, tier_label = _calculate_tier(platform)
        header_row = QHBoxLayout()
        name_lbl = QLabel(platform.get("name", "?"))
        name_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_row.addWidget(name_lbl)
        header_row.addWidget(self._tier_badge(tier_num, tier_label))
        header_row.addStretch()
        layout.addLayout(header_row)

        # Categorize capabilities
        supported = []
        partial_caps = []
        gaps = []

        for label, *keys in GAP_CHECKS:
            rating = _get_rating(platform, *keys)
            if rating == "full":
                supported.append((label, rating))
            elif rating in ("partial", "indirect", "read_only"):
                partial_caps.append((label, rating))
            else:
                gaps.append((label, rating))

        total = len(GAP_CHECKS)

        # Summary bar
        summary = QLabel(
            f"Supported: {len(supported)}/{total}   |   "
            f"Partial: {len(partial_caps)}/{total}   |   "
            f"Missing: {len(gaps)}/{total}"
        )
        summary.setStyleSheet("font-size: 13px; padding: 6px;")
        layout.addWidget(summary)

        # Supported section
        if supported:
            group = QGroupBox(f"Supported ({len(supported)})")
            g_layout = QVBoxLayout()
            for label, rating in supported:
                row = QHBoxLayout()
                row.addWidget(QLabel(f"\u2713  {label}"))
                row.addStretch()
                row.addWidget(self._rating_label(rating))
                g_layout.addLayout(row)
            group.setLayout(g_layout)
            layout.addWidget(group)

        # Partial section
        if partial_caps:
            group = QGroupBox(f"Partial / Workaround ({len(partial_caps)})")
            g_layout = QVBoxLayout()
            for label, rating in partial_caps:
                row = QHBoxLayout()
                row.addWidget(QLabel(f"\u25cb  {label}"))
                row.addStretch()
                row.addWidget(self._rating_label(rating))
                g_layout.addLayout(row)
            group.setLayout(g_layout)
            layout.addWidget(group)

        # Missing section
        if gaps:
            group = QGroupBox(f"Missing ({len(gaps)})")
            g_layout = QVBoxLayout()
            for label, rating in gaps:
                row = QHBoxLayout()
                lbl = QLabel(f"\u2717  {label}")
                lbl.setStyleSheet("color: #F44336;")
                row.addWidget(lbl)
                row.addStretch()
                row.addWidget(self._rating_label(rating))
                g_layout.addLayout(row)
            group.setLayout(g_layout)
            layout.addWidget(group)

        if not gaps and not partial_caps:
            all_good = QLabel(
                "\u2713  All CRM Builder features are fully supported!"
            )
            all_good.setStyleSheet(
                "color: #4CAF50; font-size: 14px; font-weight: bold; "
                "padding: 10px;"
            )
            layout.addWidget(all_good)

        layout.addStretch()
        return self._make_scroll_area(content)

    # ─── Pricing tab ───────────────────────────────────────────────

    def _build_pricing_tab(self) -> QWidget:
        """Build the pricing filter tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Max admin API price:"))
        self._price_spinbox = QDoubleSpinBox()
        self._price_spinbox.setRange(0, 500)
        self._price_spinbox.setValue(500)
        self._price_spinbox.setSingleStep(10)
        self._price_spinbox.setPrefix("$")
        self._price_spinbox.setSuffix(" /user/mo")
        self._price_spinbox.valueChanged.connect(self._refresh_pricing_table)
        filter_row.addWidget(self._price_spinbox)

        show_all_btn = QPushButton("Show All")
        show_all_btn.clicked.connect(lambda: self._price_spinbox.setValue(500))
        filter_row.addWidget(show_all_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Table
        self._pricing_table = QTableWidget()
        self._pricing_table.setColumnCount(6)
        self._pricing_table.setHorizontalHeaderLabels([
            "Platform", "Type", "Tier", "Free Tier",
            "Min Paid", "Admin API Price",
        ])
        self._pricing_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._pricing_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self._pricing_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._pricing_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._pricing_table)

        self._refresh_pricing_table()
        return tab

    def _refresh_pricing_table(self) -> None:
        """Repopulate the pricing table based on the current filter."""
        max_price = self._price_spinbox.value()

        # Filter and sort
        filtered = []
        for p in self._platforms:
            pricing = p.get("pricing", {})
            api_price = pricing.get("full_admin_api_per_user_month")
            if max_price >= 500:
                filtered.append(p)
            elif (
                api_price is not None
                and isinstance(api_price, (int, float))
                and api_price <= max_price
            ):
                filtered.append(p)

        def sort_key(p: dict) -> float:
            v = p.get("pricing", {}).get("full_admin_api_per_user_month")
            if v is None or not isinstance(v, (int, float)):
                return 9999
            return v

        filtered.sort(key=sort_key)

        self._pricing_table.setRowCount(len(filtered))

        for row, p in enumerate(filtered):
            pricing = p.get("pricing", {})
            tier_num, tier_label = _calculate_tier(p)
            free_tier = pricing.get("free_tier", "None")
            min_paid = pricing.get("min_paid_per_user_month")
            admin_api = pricing.get("full_admin_api_per_user_month")

            self._pricing_table.setItem(
                row, 0, QTableWidgetItem(p.get("name", "?"))
            )
            self._pricing_table.setItem(
                row, 1, QTableWidgetItem(p.get("type", ""))
            )

            tier_item = QTableWidgetItem(f"Tier {tier_num}")
            tier_color = {1: "#4CAF50", 2: "#FFC107", 3: "#FF9800", 4: "#F44336"}
            tier_item.setForeground(QColor(tier_color.get(tier_num, "#9E9E9E")))
            tier_item.setFont(QFont("", -1, QFont.Weight.Bold))
            self._pricing_table.setItem(row, 2, tier_item)

            self._pricing_table.setItem(
                row, 3, QTableWidgetItem(
                    free_tier if free_tier != "None" else "\u2014"
                )
            )
            self._pricing_table.setItem(
                row, 4, QTableWidgetItem(
                    f"${min_paid}/mo" if min_paid is not None else "\u2014"
                )
            )

            api_text = (
                f"${admin_api}/mo"
                if admin_api is not None and isinstance(admin_api, (int, float))
                else "\u2014"
            )
            self._pricing_table.setItem(
                row, 5, QTableWidgetItem(api_text)
            )

        count_label = f"{len(filtered)} of {len(self._platforms)} platforms"
        if max_price < 500:
            count_label += f" at \u2264${max_price:.0f}/user/mo"
        self.statusBar().showMessage(count_label)
