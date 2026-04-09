"""Pure-Python tree data model for the Data Browser (Section 14.8.1).

Driven by the client schema's FK relationships. No PySide6 imports.

Tree structure:
  Domains → Processes → {ProcessSteps, Requirements, ProcessEntity, ProcessField, ProcessPersona}
    Sub-domains nest under parent via parent_domain_id
    Services (is_service=TRUE) in separate "Services" branch
  Entities → {Fields → FieldOptions, Relationships, LayoutPanels → {LayoutRows, LayoutTabs}, ListColumns}
  Personas (flat)
  Decisions (flat)
  Open Issues (flat)
"""

from __future__ import annotations

import dataclasses
import sqlite3


@dataclasses.dataclass
class TreeNode:
    """A node in the navigation tree.

    :param node_id: Unique identifier for this node (e.g., "Domain:3").
    :param label: Display label.
    :param table_name: Database table (None for category nodes).
    :param record_id: Database record ID (None for category nodes).
    :param children: Child nodes.
    :param child_count: Count of child records (for badge display).
    :param expandable: Whether this node can be expanded.
    """

    node_id: str
    label: str
    table_name: str | None = None
    record_id: int | None = None
    children: list[TreeNode] = dataclasses.field(default_factory=list)
    child_count: int = 0
    expandable: bool = False


def build_tree(conn: sqlite3.Connection) -> list[TreeNode]:
    """Build the full navigation tree from the database.

    :param conn: Client database connection.
    :returns: List of top-level tree nodes.
    """
    roots: list[TreeNode] = []

    # Domains branch
    domains_node = _build_domains_branch(conn)
    if domains_node:
        roots.append(domains_node)

    # Services branch
    services_node = _build_services_branch(conn)
    if services_node:
        roots.append(services_node)

    # Entities branch
    entities_node = _build_entities_branch(conn)
    if entities_node:
        roots.append(entities_node)

    # Personas (flat)
    personas_node = _build_flat_branch(conn, "Personas", "Persona", "name")
    if personas_node:
        roots.append(personas_node)

    # Decisions (flat, sorted by identifier)
    decisions_node = _build_flat_branch(
        conn, "Decisions", "Decision", "title", order_by="identifier"
    )
    if decisions_node:
        roots.append(decisions_node)

    # Open Issues (flat, sorted by identifier)
    issues_node = _build_flat_branch(
        conn, "Open Issues", "OpenIssue", "title", order_by="identifier"
    )
    if issues_node:
        roots.append(issues_node)

    return roots


def find_node(roots: list[TreeNode], table_name: str, record_id: int) -> TreeNode | None:
    """Find a node in the tree by table name and record ID.

    :param roots: Top-level tree nodes.
    :param table_name: Database table name.
    :param record_id: Database record ID.
    :returns: The matching node, or None.
    """
    target_id = f"{table_name}:{record_id}"
    return _find_node_recursive(roots, target_id)


def _find_node_recursive(nodes: list[TreeNode], target_id: str) -> TreeNode | None:
    """Recursively search for a node by node_id."""
    for node in nodes:
        if node.node_id == target_id:
            return node
        found = _find_node_recursive(node.children, target_id)
        if found:
            return found
    return None


def filter_tree(
    roots: list[TreeNode], search_text: str
) -> list[TreeNode]:
    """Filter tree nodes by name/code/identifier.

    Returns a new tree with only matching nodes and their ancestors.

    :param roots: Top-level tree nodes.
    :param search_text: Search string (case-insensitive).
    :returns: Filtered tree nodes.
    """
    if not search_text:
        return roots
    query = search_text.lower()
    return [n for n in (_filter_node(node, query) for node in roots) if n is not None]


def _filter_node(node: TreeNode, query: str) -> TreeNode | None:
    """Recursively filter a node and its children."""
    # Check if this node matches
    matches = query in node.label.lower()

    # Filter children
    filtered_children = [
        c for c in (_filter_node(child, query) for child in node.children)
        if c is not None
    ]

    if matches or filtered_children:
        return TreeNode(
            node_id=node.node_id,
            label=node.label,
            table_name=node.table_name,
            record_id=node.record_id,
            children=filtered_children,
            child_count=len(filtered_children),
            expandable=bool(filtered_children),
        )
    return None


# ---------------------------------------------------------------------------
# Branch builders
# ---------------------------------------------------------------------------

def _build_domains_branch(conn: sqlite3.Connection) -> TreeNode | None:
    """Build the Domains category node with nested processes."""
    rows = conn.execute(
        "SELECT id, name, code, parent_domain_id FROM Domain "
        "WHERE is_service = FALSE "
        "ORDER BY sort_order, name"
    ).fetchall()
    if not rows:
        return None

    # Build parent-child map
    top_level = [r for r in rows if r[3] is None]
    children_map: dict[int, list] = {}
    for r in rows:
        parent_id = r[3]
        if parent_id is not None:
            children_map.setdefault(parent_id, []).append(r)

    domain_nodes = [
        _build_domain_node(conn, r, children_map) for r in top_level
    ]

    return TreeNode(
        node_id="category:domains",
        label="Domains",
        expandable=True,
        child_count=len(rows),
        children=domain_nodes,
    )


def _build_services_branch(conn: sqlite3.Connection) -> TreeNode | None:
    """Build the Services category node."""
    rows = conn.execute(
        "SELECT id, name, code FROM Domain WHERE is_service = TRUE ORDER BY sort_order, name"
    ).fetchall()
    if not rows:
        return None

    children_map: dict[int, list] = {}
    nodes = [_build_domain_node(conn, (*r, None), children_map) for r in rows]

    return TreeNode(
        node_id="category:services",
        label="Services",
        expandable=True,
        child_count=len(rows),
        children=nodes,
    )


def _build_domain_node(
    conn: sqlite3.Connection,
    row: tuple,
    children_map: dict[int, list],
) -> TreeNode:
    """Build a single domain node with its processes and sub-domains."""
    domain_id, name, code = row[0], row[1], row[2]

    children: list[TreeNode] = []

    # Sub-domains
    for sub_row in children_map.get(domain_id, []):
        children.append(_build_domain_node(conn, sub_row, children_map))

    # Processes
    processes = conn.execute(
        "SELECT id, name, code FROM Process WHERE domain_id = ? ORDER BY sort_order, name",
        (domain_id,),
    ).fetchall()
    for p_id, p_name, p_code in processes:
        children.append(_build_process_node(conn, p_id, p_name, p_code))

    return TreeNode(
        node_id=f"Domain:{domain_id}",
        label=f"{name} ({code})",
        table_name="Domain",
        record_id=domain_id,
        expandable=bool(children),
        child_count=len(children),
        children=children,
    )


def _build_process_node(
    conn: sqlite3.Connection, process_id: int, name: str, code: str
) -> TreeNode:
    """Build a process node with its children."""
    children: list[TreeNode] = []

    # ProcessSteps
    steps = conn.execute(
        "SELECT id, name FROM ProcessStep WHERE process_id = ? ORDER BY sort_order",
        (process_id,),
    ).fetchall()
    if steps:
        step_nodes = [
            TreeNode(
                node_id=f"ProcessStep:{s[0]}", label=s[1],
                table_name="ProcessStep", record_id=s[0],
            )
            for s in steps
        ]
        children.append(TreeNode(
            node_id=f"category:steps:{process_id}",
            label="Steps",
            expandable=True, child_count=len(step_nodes), children=step_nodes,
        ))

    # Requirements
    reqs = conn.execute(
        "SELECT id, identifier, description FROM Requirement WHERE process_id = ? ORDER BY identifier",
        (process_id,),
    ).fetchall()
    if reqs:
        req_nodes = [
            TreeNode(
                node_id=f"Requirement:{r[0]}", label=f"{r[1]}",
                table_name="Requirement", record_id=r[0],
            )
            for r in reqs
        ]
        children.append(TreeNode(
            node_id=f"category:requirements:{process_id}",
            label="Requirements",
            expandable=True, child_count=len(req_nodes), children=req_nodes,
        ))

    # Cross-references
    for xref_table, xref_label in [
        ("ProcessEntity", "Entities"),
        ("ProcessField", "Fields"),
        ("ProcessPersona", "Personas"),
    ]:
        xrefs = conn.execute(
            f"SELECT id FROM {xref_table} WHERE process_id = ?",  # noqa: S608
            (process_id,),
        ).fetchall()
        if xrefs:
            xref_nodes = [
                TreeNode(
                    node_id=f"{xref_table}:{x[0]}",
                    label=f"{xref_table} #{x[0]}",
                    table_name=xref_table, record_id=x[0],
                )
                for x in xrefs
            ]
            children.append(TreeNode(
                node_id=f"category:{xref_table.lower()}:{process_id}",
                label=xref_label,
                expandable=True, child_count=len(xref_nodes), children=xref_nodes,
            ))

    return TreeNode(
        node_id=f"Process:{process_id}",
        label=f"{name} ({code})",
        table_name="Process",
        record_id=process_id,
        expandable=bool(children),
        child_count=len(children),
        children=children,
    )


def _build_entities_branch(conn: sqlite3.Connection) -> TreeNode | None:
    """Build the Entities category node."""
    rows = conn.execute(
        "SELECT id, name, code FROM Entity ORDER BY name"
    ).fetchall()
    if not rows:
        return None

    entity_nodes = [_build_entity_node(conn, r[0], r[1], r[2]) for r in rows]

    return TreeNode(
        node_id="category:entities",
        label="Entities",
        expandable=True,
        child_count=len(rows),
        children=entity_nodes,
    )


def _build_entity_node(
    conn: sqlite3.Connection, entity_id: int, name: str, code: str
) -> TreeNode:
    """Build an entity node with its children (fields, relationships, layouts, list columns)."""
    children: list[TreeNode] = []

    # Fields → FieldOptions
    fields = conn.execute(
        "SELECT id, name, label FROM Field WHERE entity_id = ? ORDER BY sort_order, name",
        (entity_id,),
    ).fetchall()
    if fields:
        field_nodes = []
        for f_id, f_name, f_label in fields:
            # FieldOptions
            options = conn.execute(
                "SELECT id, label FROM FieldOption WHERE field_id = ? ORDER BY sort_order",
                (f_id,),
            ).fetchall()
            option_nodes = [
                TreeNode(
                    node_id=f"FieldOption:{o[0]}", label=o[1],
                    table_name="FieldOption", record_id=o[0],
                )
                for o in options
            ]
            field_nodes.append(TreeNode(
                node_id=f"Field:{f_id}",
                label=f"{f_label} ({f_name})",
                table_name="Field", record_id=f_id,
                expandable=bool(option_nodes),
                child_count=len(option_nodes),
                children=option_nodes,
            ))
        children.append(TreeNode(
            node_id=f"category:fields:{entity_id}",
            label="Fields",
            expandable=True, child_count=len(field_nodes), children=field_nodes,
        ))

    # Relationships
    rels = conn.execute(
        "SELECT id, name FROM Relationship WHERE entity_id = ? OR entity_foreign_id = ? "
        "ORDER BY name",
        (entity_id, entity_id),
    ).fetchall()
    if rels:
        rel_nodes = [
            TreeNode(
                node_id=f"Relationship:{r[0]}", label=r[1],
                table_name="Relationship", record_id=r[0],
            )
            for r in rels
        ]
        children.append(TreeNode(
            node_id=f"category:relationships:{entity_id}",
            label="Relationships",
            expandable=True, child_count=len(rel_nodes), children=rel_nodes,
        ))

    # LayoutPanels → LayoutRows, LayoutTabs
    panels = conn.execute(
        "SELECT id, label FROM LayoutPanel WHERE entity_id = ? ORDER BY sort_order",
        (entity_id,),
    ).fetchall()
    if panels:
        panel_nodes = []
        for p_id, p_label in panels:
            panel_children: list[TreeNode] = []
            # LayoutRows
            lrows = conn.execute(
                "SELECT id FROM LayoutRow WHERE panel_id = ? ORDER BY sort_order",
                (p_id,),
            ).fetchall()
            for lr in lrows:
                panel_children.append(TreeNode(
                    node_id=f"LayoutRow:{lr[0]}", label=f"Row #{lr[0]}",
                    table_name="LayoutRow", record_id=lr[0],
                ))
            # LayoutTabs
            ltabs = conn.execute(
                "SELECT id, label FROM LayoutTab WHERE panel_id = ? ORDER BY sort_order",
                (p_id,),
            ).fetchall()
            for lt_id, lt_label in ltabs:
                panel_children.append(TreeNode(
                    node_id=f"LayoutTab:{lt_id}", label=lt_label,
                    table_name="LayoutTab", record_id=lt_id,
                ))
            panel_nodes.append(TreeNode(
                node_id=f"LayoutPanel:{p_id}", label=p_label,
                table_name="LayoutPanel", record_id=p_id,
                expandable=bool(panel_children),
                child_count=len(panel_children),
                children=panel_children,
            ))
        children.append(TreeNode(
            node_id=f"category:layouts:{entity_id}",
            label="Layouts",
            expandable=True, child_count=len(panel_nodes), children=panel_nodes,
        ))

    # ListColumns
    cols = conn.execute(
        "SELECT id FROM ListColumn WHERE entity_id = ? ORDER BY sort_order",
        (entity_id,),
    ).fetchall()
    if cols:
        col_nodes = [
            TreeNode(
                node_id=f"ListColumn:{c[0]}", label=f"Column #{c[0]}",
                table_name="ListColumn", record_id=c[0],
            )
            for c in cols
        ]
        children.append(TreeNode(
            node_id=f"category:list_columns:{entity_id}",
            label="List Columns",
            expandable=True, child_count=len(col_nodes), children=col_nodes,
        ))

    return TreeNode(
        node_id=f"Entity:{entity_id}",
        label=f"{name} ({code})",
        table_name="Entity",
        record_id=entity_id,
        expandable=bool(children),
        child_count=len(children),
        children=children,
    )


def _build_flat_branch(
    conn: sqlite3.Connection,
    category_label: str,
    table_name: str,
    name_col: str,
    order_by: str | None = None,
) -> TreeNode | None:
    """Build a flat category node (e.g., Personas, Decisions, Open Issues)."""
    order = order_by or name_col
    rows = conn.execute(
        f"SELECT id, {name_col} FROM {table_name} ORDER BY {order}",  # noqa: S608
    ).fetchall()
    if not rows:
        return None

    children = [
        TreeNode(
            node_id=f"{table_name}:{r[0]}",
            label=r[1],
            table_name=table_name,
            record_id=r[0],
        )
        for r in rows
    ]
    return TreeNode(
        node_id=f"category:{table_name.lower()}",
        label=category_label,
        expandable=True,
        child_count=len(children),
        children=children,
    )
