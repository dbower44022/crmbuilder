"""CRM Platform Comparison Tool.

Loads structured YAML platform profiles and generates comparison reports.

Usage::

    # Full inventory document
    uv run python tools/crm_compare.py inventory

    # Head-to-head comparison
    uv run python tools/crm_compare.py compare salesforce zoho odoo

    # Which platforms support a capability?
    uv run python tools/crm_compare.py capability layout_management

    # What CRM Builder features are missing on a platform?
    uv run python tools/crm_compare.py gaps hubspot

    # Auto-calculated tier assessment
    uv run python tools/crm_compare.py tiers

    # Filter platforms by max price
    uv run python tools/crm_compare.py pricing --max 50

    # Validate all platform files against schema
    uv run python tools/crm_compare.py validate

    # Show platforms not reviewed in N days
    uv run python tools/crm_compare.py stale --days 180
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent / "docs" / "crm-platforms"
PLATFORMS_DIR = BASE_DIR / "platforms"
GENERATED_DIR = BASE_DIR / "generated"
SCHEMA_PATH = BASE_DIR / "schema.yaml"
REFERENCE_PATH = BASE_DIR / "reference.yaml"


def load_yaml(path: Path) -> dict:
    """Load a YAML file and return parsed dict."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_schema() -> dict:
    """Load the capability schema."""
    return load_yaml(SCHEMA_PATH)


def load_reference() -> dict:
    """Load the CRM Builder reference."""
    return load_yaml(REFERENCE_PATH)


def load_platforms(slugs: list[str] | None = None) -> list[dict]:
    """Load platform profiles, optionally filtered by slug.

    :param slugs: If provided, only load these platforms.
    :returns: List of parsed platform dicts, sorted by name.
    """
    platforms = []
    for path in sorted(PLATFORMS_DIR.glob("*.yaml")):
        data = load_yaml(path)
        if slugs and data.get("slug") not in slugs:
            continue
        data["_path"] = str(path)
        platforms.append(data)
    return sorted(platforms, key=lambda p: p.get("name", ""))


def get_rating(platform: dict, *keys: str) -> str:
    """Traverse nested dict keys to extract a rating value.

    :param platform: Platform data dict.
    :param keys: Sequence of keys to traverse.
    :returns: Rating string or "unknown".
    """
    node = platform
    for key in keys:
        if isinstance(node, dict):
            node = node.get(key)
        else:
            return "unknown"
    if node is None:
        return "unknown"
    if isinstance(node, dict):
        return node.get("rating", "unknown")
    if isinstance(node, bool):
        return "full" if node else "none"
    return str(node)


def rating_symbol(rating: str) -> str:
    """Convert a rating string to a display symbol for tables.

    :param rating: Rating string.
    :returns: Display symbol.
    """
    symbols = {
        "full": "Full",
        "partial": "Partial",
        "read_only": "Read-only",
        "indirect": "Indirect",
        "none": "None",
        "na": "N/A",
        "unknown": "—",
        "true": "Yes",
        "false": "No",
        "True": "Yes",
        "False": "No",
    }
    return symbols.get(str(rating), str(rating))


def calculate_tier(platform: dict) -> tuple[int, str]:
    """Determine the tier for a platform based on capability ratings.

    :param platform: Platform data dict.
    :returns: Tuple of (tier_number, tier_label).
    """
    entity_create = get_rating(platform, "entity_management", "create_entity")
    field_create = get_rating(platform, "field_management", "create_field")
    layout_write = get_rating(platform, "layout_management", "write_layouts")
    rel_create = get_rating(platform, "relationship_management", "create_relationship")

    if all(r == "full" for r in [entity_create, field_create, layout_write, rel_create]):
        return 1, "Full Feature Coverage"

    if field_create in ("full", "partial") and (
        entity_create in ("full", "partial", "indirect")
        or rel_create in ("full", "partial")
    ):
        return 2, "Strong but Gaps"

    if field_create in ("full", "partial"):
        return 3, "Fields Only"

    return 4, "Data API Only"


def format_price(platform: dict) -> str:
    """Format pricing summary for a platform.

    :param platform: Platform data dict.
    :returns: Formatted price string.
    """
    pricing = platform.get("pricing", {})
    free = pricing.get("free_tier", "None")
    min_paid = pricing.get("min_paid_per_user_month")
    admin_api = pricing.get("full_admin_api_per_user_month")
    parts = []
    if free and free != "None":
        parts.append(f"Free: {free}")
    if min_paid is not None:
        parts.append(f"Min: ${min_paid}/user/mo")
    if admin_api is not None and admin_api != min_paid:
        parts.append(f"Admin API: ${admin_api}/user/mo")
    return " | ".join(parts) if parts else "N/A"


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate all platform files against the schema."""
    schema = load_schema()
    valid_ratings = set(schema.get("ratings", []))  # noqa: F841 — reserved for future validation
    platforms = load_platforms()
    errors = 0

    required_keys = ["name", "slug", "type", "last_reviewed", "pricing", "api"]

    for p in platforms:
        name = p.get("name", p.get("_path", "unknown"))
        for key in required_keys:
            if key not in p:
                print(f"  ERROR: {name}: missing required key '{key}'")
                errors += 1

        reviewed = p.get("last_reviewed")
        if reviewed and not isinstance(reviewed, date):
            try:
                date.fromisoformat(str(reviewed))
            except ValueError:
                print(f"  ERROR: {name}: invalid date format for last_reviewed: {reviewed}")
                errors += 1

    if errors == 0:
        print(f"OK: {len(platforms)} platform files validated, no errors.")
    else:
        print(f"\nFound {errors} error(s) across {len(platforms)} platform files.")
    sys.exit(1 if errors else 0)


def cmd_stale(args: argparse.Namespace) -> None:
    """Show platforms not reviewed within N days."""
    cutoff = date.today() - timedelta(days=args.days)
    platforms = load_platforms()
    stale = []

    for p in platforms:
        reviewed = p.get("last_reviewed")
        if reviewed:
            if isinstance(reviewed, date):
                review_date = reviewed
            else:
                review_date = date.fromisoformat(str(reviewed))
            if review_date < cutoff:
                stale.append((p["name"], str(review_date)))
        else:
            stale.append((p["name"], "never"))

    if stale:
        print(f"Platforms not reviewed in the last {args.days} days:\n")
        for name, reviewed in sorted(stale, key=lambda x: x[1]):
            print(f"  {name}: last reviewed {reviewed}")
    else:
        print(f"All platforms reviewed within the last {args.days} days.")


def cmd_tiers(args: argparse.Namespace) -> None:
    """Display auto-calculated tier assessment."""
    platforms = load_platforms()
    tiers: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: []}

    for p in platforms:
        tier_num, _ = calculate_tier(p)
        tiers[tier_num].append(p)

    tier_labels = {
        1: "Full Feature Coverage",
        2: "Strong but Gaps",
        3: "Fields Only",
        4: "Data API Only",
    }

    print("# CRM Platform Tier Assessment\n")
    for tier_num in sorted(tiers.keys()):
        label = tier_labels[tier_num]
        plats = tiers[tier_num]
        print(f"## Tier {tier_num} — {label}\n")
        if not plats:
            print("(none)\n")
            continue

        print("| Platform | Entity Creation | Field Creation | Layout Write | Relationships | Pricing |")
        print("|----------|----------------|---------------|-------------|--------------|---------|")
        for p in sorted(plats, key=lambda x: x.get("name", "")):
            name = p.get("name", "?")
            ec = rating_symbol(get_rating(p, "entity_management", "create_entity"))
            fc = rating_symbol(get_rating(p, "field_management", "create_field"))
            lw = rating_symbol(get_rating(p, "layout_management", "write_layouts"))
            rc = rating_symbol(get_rating(p, "relationship_management", "create_relationship"))
            price = format_price(p)
            print(f"| **{name}** | {ec} | {fc} | {lw} | {rc} | {price} |")
        print()


def cmd_compare(args: argparse.Namespace) -> None:
    """Generate head-to-head comparison of specified platforms."""
    platforms = load_platforms(args.platforms)
    if not platforms:
        print(f"No platforms found matching: {args.platforms}")
        sys.exit(1)

    names = [p["name"] for p in platforms]
    header = "| Capability | " + " | ".join(f"**{n}**" for n in names) + " |"
    sep = "|------------|" + "|".join("-" * (len(n) + 4) for n in names) + "|"

    print(f"# CRM Comparison: {', '.join(names)}\n")
    print(f"Generated: {date.today().isoformat()}\n")

    sections = [
        ("API & Auth", [
            ("Protocol", lambda p: ", ".join(p.get("api", {}).get("protocol", []))),
            ("Auth", lambda p: ", ".join(p.get("api", {}).get("auth_methods", []))),
            ("Rate Limit", lambda p: p.get("api", {}).get("rate_limit", "—")),
        ]),
        ("Entity Management", [
            ("Create Entity", lambda p: rating_symbol(get_rating(p, "entity_management", "create_entity"))),
            ("Delete Entity", lambda p: rating_symbol(get_rating(p, "entity_management", "delete_entity"))),
            ("Entity Types", lambda p: _entity_types_str(p)),
            ("Cache Rebuild", lambda p: rating_symbol(get_rating(p, "entity_management", "cache_rebuild"))),
        ]),
        ("Field Management", [
            ("Create Field", lambda p: rating_symbol(get_rating(p, "field_management", "create_field"))),
            ("Update Field", lambda p: rating_symbol(get_rating(p, "field_management", "update_field"))),
            ("All 14 Types", lambda p: _all_types_str(p)),
        ]),
        ("Layout Management", [
            ("Read Layouts", lambda p: rating_symbol(get_rating(p, "layout_management", "read_layouts"))),
            ("Write Layouts", lambda p: rating_symbol(get_rating(p, "layout_management", "write_layouts"))),
            ("Detail View", lambda p: _bool_str(p, "layout_management", "detail_view")),
            ("List View", lambda p: _bool_str(p, "layout_management", "list_view")),
            ("Panels/Sections", lambda p: _bool_str(p, "layout_management", "panels")),
            ("Tabs", lambda p: _bool_str(p, "layout_management", "tabs")),
            ("Conditional Visibility", lambda p: _bool_str(p, "layout_management", "conditional_visibility")),
        ]),
        ("Relationship Management", [
            ("Create Relationship", lambda p: rating_symbol(get_rating(p, "relationship_management", "create_relationship"))),
            ("One-to-Many", lambda p: _bool_str(p, "relationship_management", "one_to_many")),
            ("Many-to-Many", lambda p: _bool_str(p, "relationship_management", "many_to_many")),
            ("Link Labels", lambda p: _bool_str(p, "relationship_management", "link_labels")),
            ("Cascade Delete", lambda p: _bool_str(p, "relationship_management", "cascade_delete")),
        ]),
        ("Data Operations", [
            ("Create Record", lambda p: rating_symbol(get_rating(p, "data_operations", "create_record"))),
            ("Search by Email", lambda p: rating_symbol(get_rating(p, "data_operations", "search_by_email"))),
            ("Upsert", lambda p: rating_symbol(get_rating(p, "data_operations", "upsert"))),
            ("Batch Create", lambda p: rating_symbol(get_rating(p, "data_operations", "batch_create"))),
            ("Query Language", lambda p: _query_lang_str(p)),
        ]),
        ("Pricing", [
            ("Free/Dev Tier", lambda p: p.get("pricing", {}).get("free_tier", "None")),
            ("Min Paid", lambda p: f"${p['pricing']['min_paid_per_user_month']}/user/mo" if p.get("pricing", {}).get("min_paid_per_user_month") else "—"),
            ("Full Admin API", lambda p: f"${p['pricing']['full_admin_api_per_user_month']}/user/mo" if p.get("pricing", {}).get("full_admin_api_per_user_month") is not None else "—"),
        ]),
    ]

    for section_name, rows in sections:
        print(f"\n### {section_name}\n")
        print(header)
        print(sep)
        for row_label, extractor in rows:
            values = [str(extractor(p)) for p in platforms]
            print(f"| {row_label} | " + " | ".join(values) + " |")


def _entity_types_str(p: dict) -> str:
    """Extract entity types as display string."""
    em = p.get("entity_management", {})
    et = em.get("entity_types", {})
    if isinstance(et, dict):
        available = et.get("available", [])
        if available:
            return ", ".join(str(a) for a in available)
    return "—"


def _all_types_str(p: dict) -> str:
    """Check if platform supports all 14 CRM Builder field types."""
    fm = p.get("field_management", {})
    if fm.get("all_current_types_supported"):
        return "Yes"
    ft = fm.get("field_types", {})
    if isinstance(ft, dict) and len(ft) >= 14:
        return "Yes"
    return "Partial" if ft else "—"


def _bool_str(p: dict, *keys: str) -> str:
    """Extract a boolean-ish value as Yes/No/—."""
    node = p
    for key in keys:
        if isinstance(node, dict):
            node = node.get(key)
        else:
            return "—"
    if node is None:
        return "—"
    if isinstance(node, dict):
        val = node.get("supported", node.get("rating"))
        if val is None:
            return "—"
        if isinstance(val, bool):
            return "Yes" if val else "No"
        return rating_symbol(str(val))
    if isinstance(node, bool):
        return "Yes" if node else "No"
    return rating_symbol(str(node))


def _query_lang_str(p: dict) -> str:
    """Extract query language name."""
    do = p.get("data_operations", {})
    ql = do.get("query_language")
    if isinstance(ql, dict):
        return ql.get("name", "—")
    if isinstance(ql, str):
        return ql
    return "—"


def cmd_capability(args: argparse.Namespace) -> None:
    """Show which platforms support a specific capability."""
    cap = args.capability
    platforms = load_platforms()

    cap_parts = cap.split(".")
    print(f"# Capability: {cap}\n")
    print("| Platform | Rating | Min Edition | Method / Notes |")
    print("|----------|--------|------------|----------------|")

    for p in platforms:
        node = p
        for part in cap_parts:
            if isinstance(node, dict):
                node = node.get(part)
            else:
                node = None
                break

        if node is None:
            rating = "unknown"
            edition = "—"
            method = "—"
        elif isinstance(node, dict):
            rating = node.get("rating", "unknown")
            edition = node.get("min_edition", "—")
            method = node.get("method", node.get("notes", "—"))
        elif isinstance(node, bool):
            rating = "full" if node else "none"
            edition = "—"
            method = "—"
        else:
            rating = str(node)
            edition = "—"
            method = "—"

        print(f"| **{p['name']}** | {rating_symbol(rating)} | {edition} | {method} |")


def cmd_gaps(args: argparse.Namespace) -> None:
    """Show what CRM Builder features a platform is missing."""
    platforms = load_platforms([args.platform])
    if not platforms:
        print(f"Platform '{args.platform}' not found.")
        sys.exit(1)

    p = platforms[0]
    print(f"# CRM Builder Feature Gaps: {p['name']}\n")
    print(f"Generated: {date.today().isoformat()}\n")

    checks = [
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
        ("Record Create", "data_operations", "create_record"),
        ("Record Update", "data_operations", "update_record"),
        ("Search by Email", "data_operations", "search_by_email"),
    ]

    supported = []
    gaps = []
    partial_caps = []

    for label, *keys in checks:
        rating = get_rating(p, *keys)
        if rating == "full":
            supported.append(label)
        elif rating in ("partial", "indirect", "read_only"):
            partial_caps.append((label, rating))
        else:
            gaps.append((label, rating))

    print(f"### Supported ({len(supported)} of {len(checks)})\n")
    for label in supported:
        print(f"- {label}")

    if partial_caps:
        print(f"\n### Partial / Workaround ({len(partial_caps)})\n")
        for label, rating in partial_caps:
            print(f"- {label}: **{rating_symbol(rating)}**")

    if gaps:
        print(f"\n### Missing ({len(gaps)})\n")
        for label, rating in gaps:
            print(f"- {label}: **{rating_symbol(rating)}**")
    else:
        print("\nNo gaps — all CRM Builder features are supported!")

    # Field type coverage
    print("\n### Field Type Coverage\n")
    ft = p.get("field_management", {}).get("field_types", {})
    schema = load_schema()
    current_types = schema.get("field_types", {}).get("current", [])

    if ft:
        missing_types = [t for t in current_types if t not in ft]
        if missing_types:
            print(f"Missing field types: {', '.join(missing_types)}")
        else:
            print("All 14 CRM Builder field types have equivalents.")
    else:
        print("Field type mapping not available for this platform.")


def cmd_pricing(args: argparse.Namespace) -> None:
    """Filter platforms by maximum price point."""
    platforms = load_platforms()
    max_price = args.max

    print(f"# Platforms with Admin API at ${max_price}/user/month or less\n")
    print("| Platform | Free Tier | Admin API Price | Tier |")
    print("|----------|-----------|----------------|------|")

    matches = []
    for p in platforms:
        pricing = p.get("pricing", {})
        api_price = pricing.get("full_admin_api_per_user_month")
        if api_price is not None and isinstance(api_price, (int, float)) and api_price <= max_price:
            tier_num, tier_label = calculate_tier(p)
            free = pricing.get("free_tier", "None")
            matches.append((p["name"], free, api_price, tier_num, tier_label))

    for name, free, price, tier_num, tier_label in sorted(matches, key=lambda x: x[2]):
        print(f"| **{name}** | {free} | ${price}/user/mo | Tier {tier_num}: {tier_label} |")

    if not matches:
        print("| (no matches) | | | |")


def cmd_inventory(args: argparse.Namespace) -> None:
    """Generate the full inventory Markdown document."""
    platforms = load_platforms()
    today = date.today().isoformat()

    lines = []

    def w(line: str = "") -> None:
        lines.append(line)

    w("# CRM Platform API Capability Inventory")
    w()
    w(f"> **Generated:** {today} by `crm_compare.py inventory`")
    w(f"> **Platforms:** {len(platforms)}")
    w("> **Source data:** `docs/crm-platforms/platforms/*.yaml`")
    w()
    w("---")
    w()

    # Platform overview table
    w("## Platform Overview")
    w()
    w("| Platform | Type | API Protocol | Auth | Free/Dev Tier |")
    w("|----------|------|-------------|------|--------------|")
    for p in platforms:
        name = p.get("name", "?")
        ptype = p.get("type", "—")
        proto = ", ".join(p.get("api", {}).get("protocol", []))
        auth = ", ".join(p.get("api", {}).get("auth_methods", []))
        free = p.get("pricing", {}).get("free_tier", "None")
        w(f"| **{name}** | {ptype} | {proto} | {auth} | {free} |")
    w()

    # Tier assessment
    w("## Tier Assessment")
    w()
    tiers: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: []}
    for p in platforms:
        tier_num, _ = calculate_tier(p)
        tiers[tier_num].append(p)

    tier_labels = {
        1: "Full Feature Coverage — entity, field, layout, and relationship CRUD via API",
        2: "Strong but Gaps — most capabilities via API, missing layout or entity creation",
        3: "Fields Only — custom field creation via API, no entity/layout/relationship",
        4: "Data API Only — record CRUD only, no schema management",
    }

    for tier_num in sorted(tiers.keys()):
        plats = tiers[tier_num]
        label = tier_labels[tier_num]
        w(f"### Tier {tier_num} — {label}")
        w()
        if plats:
            for p in sorted(plats, key=lambda x: x.get("name", "")):
                price = format_price(p)
                w(f"- **{p['name']}** — {price}")
        else:
            w("(none)")
        w()

    # Core capability matrix
    w("## Core Capability Matrix")
    w()

    cap_rows = [
        ("Create Entity", "entity_management", "create_entity"),
        ("Delete Entity", "entity_management", "delete_entity"),
        ("Create Field", "field_management", "create_field"),
        ("Update Field", "field_management", "update_field"),
        ("Read Layout", "layout_management", "read_layouts"),
        ("Write Layout", "layout_management", "write_layouts"),
        ("Create Relationship", "relationship_management", "create_relationship"),
        ("Create Record", "data_operations", "create_record"),
        ("Search by Email", "data_operations", "search_by_email"),
        ("Batch/Bulk Import", "data_operations", "batch_create"),
    ]

    name_col = [p.get("name", "?") for p in platforms]
    w("| Capability | " + " | ".join(f"**{n}**" for n in name_col) + " |")
    w("|------------|" + "|".join("-" * (len(n) + 4) for n in name_col) + "|")

    for label, *keys in cap_rows:
        vals = [rating_symbol(get_rating(p, *keys)) for p in platforms]
        w(f"| {label} | " + " | ".join(vals) + " |")
    w()

    # Layout detail
    w("## Layout Management Detail")
    w()
    layout_rows = [
        ("Read Layouts", "layout_management", "read_layouts"),
        ("Write Layouts", "layout_management", "write_layouts"),
        ("Detail View", "layout_management", "detail_view"),
        ("Edit View", "layout_management", "edit_view"),
        ("List View", "layout_management", "list_view"),
        ("Panels/Sections", "layout_management", "panels"),
        ("Tabs", "layout_management", "tabs"),
        ("Conditional Visibility", "layout_management", "conditional_visibility"),
    ]

    w("| Capability | " + " | ".join(f"**{n}**" for n in name_col) + " |")
    w("|------------|" + "|".join("-" * (len(n) + 4) for n in name_col) + "|")
    for label, *keys in layout_rows:
        vals = [_bool_str(p, *keys) for p in platforms]
        w(f"| {label} | " + " | ".join(vals) + " |")
    w()

    # Relationship detail
    w("## Relationship Management Detail")
    w()
    rel_rows = [
        ("Create Relationship", "relationship_management", "create_relationship"),
        ("One-to-Many", "relationship_management", "one_to_many"),
        ("Many-to-Many", "relationship_management", "many_to_many"),
        ("Link Labels", "relationship_management", "link_labels"),
        ("Audit Both Sides", "relationship_management", "audit_both_sides"),
        ("Cascade Delete", "relationship_management", "cascade_delete"),
        ("Polymorphic", "relationship_management", "polymorphic"),
    ]

    w("| Capability | " + " | ".join(f"**{n}**" for n in name_col) + " |")
    w("|------------|" + "|".join("-" * (len(n) + 4) for n in name_col) + "|")
    for label, *keys in rel_rows:
        vals = [_bool_str(p, *keys) for p in platforms]
        w(f"| {label} | " + " | ".join(vals) + " |")
    w()

    # Future capabilities
    w("## Future Capabilities")
    w()
    future_rows = [
        ("Workflow Rules", "workflow_automation", "create_rules"),
        ("Flows/Automation", "workflow_automation", "create_flows"),
        ("Approval Processes", "workflow_automation", "approval_processes"),
        ("Create Roles", "roles_permissions", "create_roles"),
        ("Field-Level Security", "roles_permissions", "field_level_security"),
        ("Dashboards", "dashboards_reports", "create_dashboards"),
        ("Reports", "dashboards_reports", "create_reports"),
        ("Email Templates", "email_templates", "crud_templates"),
        ("Webhooks", "webhooks_events", "outbound_webhooks"),
        ("Event Subscriptions", "webhooks_events", "event_subscriptions"),
    ]

    w("| Capability | " + " | ".join(f"**{n}**" for n in name_col) + " |")
    w("|------------|" + "|".join("-" * (len(n) + 4) for n in name_col) + "|")
    for label, *keys in future_rows:
        vals = [rating_symbol(get_rating(p, *keys)) for p in platforms]
        w(f"| {label} | " + " | ".join(vals) + " |")
    w()

    # Pricing
    w("## Pricing Summary")
    w()
    w("| Platform | Free Tier | Min Paid | Full Admin API | Enterprise |")
    w("|----------|-----------|----------|---------------|-----------|")
    for p in platforms:
        pricing = p.get("pricing", {})
        free = pricing.get("free_tier", "None")
        min_p = f"${pricing['min_paid_per_user_month']}/user/mo" if pricing.get("min_paid_per_user_month") else "—"
        admin = f"${pricing['full_admin_api_per_user_month']}/user/mo" if pricing.get("full_admin_api_per_user_month") is not None else "—"
        ent = f"${pricing['enterprise_per_user_month']}/user/mo" if pricing.get("enterprise_per_user_month") else "—"
        w(f"| **{p['name']}** | {free} | {min_p} | {admin} | {ent} |")
    w()

    w("---")
    w()
    w(f"*Generated {today} from {len(platforms)} platform profiles by `tools/crm_compare.py`*")

    output = "\n".join(lines) + "\n"

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GENERATED_DIR / "crm-platform-inventory.md"
    out_path.write_text(output, encoding="utf-8")
    print(f"Inventory written to {out_path} ({len(platforms)} platforms)")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CRM Platform Comparison Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inventory", help="Generate full inventory document")
    sub.add_parser("validate", help="Validate platform files against schema")
    sub.add_parser("tiers", help="Show auto-calculated tier assessment")

    compare_p = sub.add_parser("compare", help="Head-to-head comparison")
    compare_p.add_argument("platforms", nargs="+", help="Platform slugs to compare")

    cap_p = sub.add_parser("capability", help="Show platforms supporting a capability")
    cap_p.add_argument("capability", help="Dotted capability path (e.g., layout_management.write_layouts)")

    gaps_p = sub.add_parser("gaps", help="Show CRM Builder feature gaps for a platform")
    gaps_p.add_argument("platform", help="Platform slug")

    pricing_p = sub.add_parser("pricing", help="Filter platforms by price")
    pricing_p.add_argument("--max", type=float, required=True, help="Max price per user/month")

    stale_p = sub.add_parser("stale", help="Show platforms not reviewed recently")
    stale_p.add_argument("--days", type=int, default=180, help="Days threshold (default: 180)")

    args = parser.parse_args()

    commands = {
        "inventory": cmd_inventory,
        "validate": cmd_validate,
        "tiers": cmd_tiers,
        "compare": cmd_compare,
        "capability": cmd_capability,
        "gaps": cmd_gaps,
        "pricing": cmd_pricing,
        "stale": cmd_stale,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
