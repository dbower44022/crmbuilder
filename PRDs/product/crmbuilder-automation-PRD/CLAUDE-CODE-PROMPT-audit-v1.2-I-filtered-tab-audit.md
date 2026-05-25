# CLAUDE-CODE-PROMPT — audit-v1.2-I — Filtered-Tab Audit Capture

**Repo:** `crmbuilder`
**Series:** `audit-v1.2` (eleven-prompt sequence implementing the v1.2
expansion of the Audit feature per
`PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` v1.3)
**Last Updated:** 05-24-26 08:00
**Spec:** Schema doesn't have a dedicated filtered-tab section
distinct from the existing v1.1 surface; `FilteredTab` dataclass in
`espo_impl/core/models.py` is the authoritative shape this prompt
reverse-engineers.
**Planning:** `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md`
§5 Prompt I.
**Depends on:** Prompt H (commit `3a9aacdc` — audit-side discovery
infrastructure, `_client_v15` migration head, `AuditOptions` extended
with security flag). No Prompt G dependency (filtered tabs are
independent of role-aware visibility).
**Governance:** No new decisions in this prompt. Carries forward the
seven DECs accumulated for this conversation's close-out.

## Position in the Series

This is **Prompt I — the filtered-tab audit half.** The deploy side
(`filtered_tab_manager.py`) has been in the codebase since v1.1
shipped; what's missing is the audit-side reverse-engineering of the
two-half EspoCRM pattern: Report Filter records (REST-writable when
Advanced Pack is present) plus scope/clientDefs metadata files
(filesystem-only). The audit reads both halves and emits structured
`filteredTabs:` blocks into the existing per-entity YAML output.

After this prompt:

- **Prompt J** adds the entity-picker UI, security checkbox, and
  overwrite-confirmation dialog in the Audit dialog
- **Prompt K** documentation updates (`feat-audit.md` v1.2 and
  user-guide)

**This prompt does NOT implement:**

- Schema-doc edits — the existing v1.1 `filteredTabs:` shape on
  `EntityDefinition` is the target; no schema changes needed
- Pipeline integration — audit-side already runs in `run_audit()`;
  this prompt slots a new step in between relationships discovery
  (Step 3) and security discovery (Step 3.5 from Prompt H), making
  it Step 3.4 by convention
- Audit-side reverse engineering of relative-date tokens — by the
  time a filter has deployed, relative tokens have been resolved
  to absolute `YYYY-MM-DD` strings; audit emits the absolute form
  and operators may manually convert back to relative tokens if
  desired. Documented in the prompt; not implemented as inference
  logic
- UI changes — Prompt J
- Documentation — Prompt K

## 1. EspoCRM Filtered-Tab Wire Architecture

Documented inline since the deploy half is a v1.1-era module the
audit needs to reverse cleanly. Future readers benefit from a single
source of truth describing the round-trip.

A filtered tab on EspoCRM 9.x consists of three artifacts:

1. **Report Filter record** (Advanced Pack extension): a database
   record at `/api/v1/ReportFilter` with shape
   `{name, entityType, data.where}`. The `where` field carries the
   filter criteria as a list of EspoCRM where-items.
2. **scopes/<Scope>.json**: a metadata file registering the scope
   as a tab. Shape: `{entity: false, tab: true, acl: <strategy>,
   disabled: false, module: "Custom", isCustom: true}`. Written to
   the EspoCRM server filesystem; readable via the `Metadata` API.
3. **clientDefs/<Scope>.json**: a metadata file binding the scope
   to the Report Filter and identifying its target entity. Shape:
   `{controller: "record", entity: <wireName>, defaultFilter:
   "reportFilter<id>"}`. Also filesystem-only-writable but
   readable via the `Metadata` API.
4. **i18n/en_US/Global.json**: a label patch under
   `scopeNames.<Scope>` that gives the navigation entry its
   human-readable label.

The audit needs all four to recover a `FilteredTab` dataclass. Each
piece is readable via the existing API:

- `client.get_all_scopes()` returns all scopes including custom
  tab-scopes (filter by `isCustom: true` AND `tab: true` AND
  `entity: false`).
- `client.get_client_defs(scope_name)` returns the per-scope
  clientDefs — including the entity binding and Report Filter ID
  reference.
- `client.list_report_filters(entity_wire_name)` returns the Report
  Filter records for an entity. Returns HTTP 404 when Advanced Pack
  isn't installed; the audit treats this as "no filtered tabs
  available on this instance" and continues gracefully.
- `audit_manager._ensure_i18n()` and the existing i18n lookups
  recover the labels.

## 2. Filter AST Reverse Translation

The deploy-side `filtered_tab_manager._to_where_items` /
`_node_to_where` / `_leaf_to_where` (lines 349–435) translates the
parsed YAML condition AST to EspoCRM where-items. Prompt I needs
the inverse:

| EspoCRM where-item | Parsed AST node |
| --- | --- |
| `{type: "and", value: [...]}` | `AllNode(children=[...])` |
| `{type: "or", value: [...]}` | `AnyNode(children=[...])` |
| `{type: "currentUser", attribute: F}` | `LeafClause(field=F, op="equals", value="$user")` |
| `{type: "notCurrentUser", attribute: F}` | `LeafClause(field=F, op="notEquals", value="$user")` |
| `{type: "isNull"/"isNotNull", attribute: F}` | `LeafClause(field=F, op=type)` (no value) |
| `{type: <op>, attribute: F, value: V}` | `LeafClause(field=F, op=type, value=V)` |

**Top-level wrapping.** EspoCRM's top-level `data.where` is always a
list of where-items. The deploy side wraps a single leaf in a
one-element list. Reversing:

- One-element list → unwrap and recurse on the single item (preserves
  the YAML-natural shape: a single leaf returns a single `LeafClause`,
  not `AllNode([LeafClause])`)
- Multi-element list → wrap children in implicit `AllNode` (the
  schema's shorthand-list form). This matches the YAML reading where
  a top-level list of items is implicitly AND'd

**Relative-date tokens are NOT reverse-engineered.** Post-deploy, the
filter's date values are absolute `YYYY-MM-DD` strings.
`relative_date.is_relative_date()` returns False for absolute
dates. The audit emits absolute dates verbatim into the YAML
output; operators who want relative tokens (Section 11) edit them
in by hand after import. Documented in the prompt and emitted as
an informational log line during audit when any filter contains
date values.

**Unknown where-item types.** EspoCRM has where-item types beyond
the schema's vocabulary (e.g., `today`, `currentMonth`, etc.). For
each unknown type encountered, the audit emits a warning and skips
the entire filter for that tab — the tab is captured (label,
scope) but without a `filter:` block. The operator can hand-write
the missing filter post-import. Better than a partial filter that
silently drops conditions.

## Scope

In scope:

1. `espo_impl/core/audit_manager.py`:
   - Extend `AuditOptions` with `include_filtered_tabs: bool = True`
     per DEC-180
   - Add `FilteredTabAuditResult` dataclass
   - Extend `EntityAuditResult` with
     `filtered_tabs: list[FilteredTabAuditResult]` collection
   - Add `_discover_filtered_tabs()` method — orchestrates the
     two-half discovery using `get_all_scopes`, `get_client_defs`,
     and `list_report_filters`
   - Add `_reverse_where_items()` helper — list→AST inverse of
     `filtered_tab_manager._to_where_items`
   - Add `_reverse_where_item()` helper — single where-item→AST
     inverse of `_node_to_where` / `_leaf_to_where`
   - Wire into `run_audit()` as Step 3.4 (between relationship
     discovery and security discovery)
   - Extend `_write_yaml_files` so per-entity YAML output includes
     `filteredTabs:` blocks under the entity's existing structure
2. `automation/db/migrations.py`:
   - Add `_client_v16(conn)` migration creating the `FilteredTab`
     client-DB table
   - Append `(16, _client_v16)` to `CLIENT_MIGRATIONS` list
3. `espo_impl/core/audit_db.py`:
   - Add `_insert_filtered_tab()` helper
   - Wire into `insert_audit_records()` per-entity (or post-entity,
     since filtered tabs are entity-scoped)
4. Tests:
   - `tests/test_audit_manager.py` — discovery flow,
     reverse-translation, 404/no-Advanced-Pack graceful handling,
     unknown-where-item-type warning, mixed-result batch
   - `tests/test_audit_db.py` — filtered-tab insertion
   - `tests/db/test_client_migrations.py` — `_client_v16`
     idempotency and schema

Out of scope:

- Schema-doc edits (no schema changes)
- Pipeline integration in `run_worker.py` (audit-side, not
  deploy-side)
- UI work — Prompt J
- Documentation — Prompt K
- Reverse-engineering of relative-date tokens — operators
  manually edit YAML for that

## Working Method

Standard CRM Builder Python conventions:

```bash
uv run ruff check espo_impl/ automation/db/ tests/
uv run pytest tests/ -v
```

**Precedents.**

- Prompt H's `_discover_roles` / `_discover_teams` for the
  discovery-method shape
- `filtered_tab_manager._to_where_items` / `_node_to_where` /
  `_leaf_to_where` for the deploy-direction translation (this
  prompt mirrors it in the opposite direction)
- `_client_v15` from Prompt H for the migration shape and the
  Instance-table-existence guard
- `audit_manager._reverse_dynamic_logic` (existing, line 717) is a
  structural template for the reverse-where-items helper — both are
  pure functions on the captured wire data

## Files to Modify

### 1. `espo_impl/core/audit_manager.py` — discovery + reverse-translation + YAML emission

**Extend `AuditOptions`** (add new boolean):

```python
@dataclass
class AuditOptions:
    """Options controlling what the audit captures."""

    include_custom_fields: bool = True
    include_native_custom_fields: bool = True
    include_detail_layouts: bool = True
    include_list_layouts: bool = True
    include_relationships: bool = True
    include_native_fields: bool = False
    include_security: bool = True
    include_filtered_tabs: bool = True  # NEW per DEC-180
```

**Add `FilteredTabAuditResult` dataclass.** Place after
`RoleAuditResult` / `TeamAuditResult` from Prompt H:

```python
@dataclass
class FilteredTabAuditResult:
    """Result of auditing a single filtered tab.

    Mirrors the YAML-side ``FilteredTab`` dataclass shape (in
    ``models.py``). The filter AST is captured in parsed form so
    YAML emission can render it canonically; downstream consumers
    can pickle/serialize as needed.

    :param id: Stable identifier (derived from scope name, lower-
        cased and kebab-style if the scope is PascalCase).
    :param scope: PascalCase scope name from the EspoCRM metadata
        (e.g., ``MyEngagements``).
    :param label: Human-readable label from i18n
        ``Global.scopeNames``.
    :param filter: Parsed condition AST recovered from the Report
        Filter's ``data.where``. May be None if the filter
        contained unknown where-item types (audit warning emitted;
        operator edits in YAML after import).
    :param nav_order: Ordinal position if recoverable from
        tabList metadata; None otherwise (the deploy half also
        treats this as optional).
    :param acl: ACL strategy from ``scopes/<Scope>.json``; defaults
        to ``"boolean"`` matching the deploy-side default.
    """

    id: str
    scope: str
    label: str
    filter: "ConditionNode | None" = None
    nav_order: int | None = None
    acl: str = "boolean"
```

**Extend `EntityAuditResult`** with a filtered-tab collection:

```python
@dataclass
class EntityAuditResult:
    # ... existing fields ...
    filtered_tabs: list[FilteredTabAuditResult] = field(default_factory=list)
```

**Add `_discover_filtered_tabs`** method on `AuditManager`. Place
after the relationship-discovery method:

```python
def _discover_filtered_tabs(
    self,
    entities: list[EntityAuditResult],
    report: AuditReport,
) -> None:
    """Discover filtered tabs on the source instance.

    Walks all scopes to find custom tab-scopes, queries clientDefs
    for each to recover the entity binding and Report Filter ID,
    then matches against Report Filter records per audited entity.
    Mutates each ``EntityAuditResult.filtered_tabs`` in place.

    HTTP 404 from ``list_report_filters`` means Advanced Pack is
    not installed; the method skips silently and logs an
    informational note rather than recording an error.

    :param entities: Audited entities to attach filtered tabs to.
    :param report: For warning / error accumulation.
    """
    from espo_impl.core.audit_utils import strip_entity_c_prefix

    # Step 1: Find all custom tab scopes
    status, all_scopes = self._client.get_all_scopes()
    if status != 200 or not isinstance(all_scopes, dict):
        report.warnings.append(
            f"Failed to fetch scopes for filtered-tab discovery "
            f"(HTTP {status})"
        )
        return

    tab_scopes: list[str] = []
    for scope_name, scope_def in all_scopes.items():
        if not isinstance(scope_def, dict):
            continue
        if (
            scope_def.get("tab") is True
            and scope_def.get("isCustom") is True
            and scope_def.get("entity") is False
        ):
            tab_scopes.append(scope_name)

    if not tab_scopes:
        return  # No tab scopes; nothing to capture

    # Step 2: For each tab scope, get its clientDefs binding
    bindings: list[tuple[str, str, str, str]] = []
    # tuples of (scope_name, entity_wire_name, report_filter_id, acl)
    for scope_name in tab_scopes:
        status, client_defs = self._client.get_client_defs(scope_name)
        if status != 200 or not isinstance(client_defs, dict):
            report.warnings.append(
                f"Failed to fetch clientDefs for scope '{scope_name}' "
                f"(HTTP {status}); skipped"
            )
            continue
        entity_wire = client_defs.get("entity")
        default_filter = client_defs.get("defaultFilter", "")
        if not isinstance(entity_wire, str) or not entity_wire:
            continue
        if not isinstance(default_filter, str) or not default_filter.startswith("reportFilter"):
            continue
        report_filter_id = default_filter[len("reportFilter"):]
        acl = "boolean"
        scope_def = all_scopes.get(scope_name, {})
        if isinstance(scope_def, dict):
            acl_val = scope_def.get("acl")
            if isinstance(acl_val, str):
                acl = acl_val
        bindings.append((scope_name, entity_wire, report_filter_id, acl))

    if not bindings:
        return

    # Step 3: Index bindings by entity
    bindings_by_entity: dict[str, list[tuple[str, str, str]]] = {}
    for scope_name, entity_wire, report_filter_id, acl in bindings:
        bindings_by_entity.setdefault(entity_wire, []).append(
            (scope_name, report_filter_id, acl),
        )

    # Step 4: For each entity in the audit, fetch its Report Filters
    # and reverse-translate
    for entity in entities:
        entity_bindings = bindings_by_entity.get(entity.espo_name)
        if not entity_bindings:
            continue

        status, body = self._client.list_report_filters(entity.espo_name)
        if status == 404:
            # Advanced Pack not installed — graceful no-op
            self._cb(
                "[AUDIT]    Note: Advanced Pack not installed; "
                "filtered-tab criteria not auditable.",
                "yellow",
            )
            continue
        if status != 200 or not isinstance(body, dict):
            report.warnings.append(
                f"Failed to fetch Report Filters for "
                f"'{entity.yaml_name}' (HTTP {status})"
            )
            continue

        # Index Report Filters by id for fast lookup
        filters_by_id: dict[str, dict[str, Any]] = {}
        for rf in body.get("list", []):
            if isinstance(rf, dict) and isinstance(rf.get("id"), str):
                filters_by_id[rf["id"]] = rf

        for scope_name, report_filter_id, acl in entity_bindings:
            rf = filters_by_id.get(report_filter_id)
            if rf is None:
                # Binding exists but Report Filter is missing — log and skip
                report.warnings.append(
                    f"Scope '{scope_name}' binds to Report Filter "
                    f"'{report_filter_id}' but that record was not "
                    f"found; skipped"
                )
                continue

            # Reverse-translate the where clause
            data = rf.get("data") or {}
            where = data.get("where") if isinstance(data, dict) else None
            filter_ast = self._reverse_where_items(where, report, scope_name)

            # Recover the label from i18n
            label = rf.get("name") or scope_name
            global_block = self._i18n.get("Global", {}) if isinstance(self._i18n, dict) else {}
            scope_names = global_block.get("scopeNames", {}) if isinstance(global_block, dict) else {}
            label_from_i18n = scope_names.get(scope_name) if isinstance(scope_names, dict) else None
            if isinstance(label_from_i18n, str) and label_from_i18n:
                label = label_from_i18n

            tab_id = scope_name[0].lower() + scope_name[1:] if scope_name else scope_name
            entity.filtered_tabs.append(FilteredTabAuditResult(
                id=tab_id,
                scope=scope_name,
                label=label,
                filter=filter_ast,
                nav_order=None,
                acl=acl,
            ))
```

**Add `_reverse_where_items` and `_reverse_where_item` helpers.**
Place after the existing `_reverse_dynamic_logic` method:

```python
def _reverse_where_items(
    self,
    where: list | None,
    report: AuditReport,
    context_label: str,
) -> "ConditionNode | None":
    """Reverse-translate a list of EspoCRM where-items to an AST root.

    Inverse of ``filtered_tab_manager._to_where_items``.

    :param where: The Report Filter's ``data.where`` list.
    :param report: For warning accumulation on unknown types.
    :param context_label: Tab label/scope for warning attribution.
    :returns: Root AST node, or None if the list is empty or
        contained only unknown where-item types.
    """
    from espo_impl.core.condition_expression import AllNode, ConditionNode

    if not isinstance(where, list) or not where:
        return None

    converted: list[ConditionNode] = []
    skipped_unknown = False
    for item in where:
        node = self._reverse_where_item(item, report, context_label)
        if node is None:
            skipped_unknown = True
            continue
        converted.append(node)

    if skipped_unknown:
        report.warnings.append(
            f"Filtered tab '{context_label}': filter contained "
            f"unknown where-item types; filter omitted from YAML "
            f"output (tab still captured with label and scope)"
        )
        return None

    if not converted:
        return None
    if len(converted) == 1:
        return converted[0]
    return AllNode(children=converted)


def _reverse_where_item(
    self,
    item: dict | None,
    report: AuditReport,
    context_label: str,
) -> "ConditionNode | None":
    """Reverse-translate a single EspoCRM where-item to an AST node.

    Inverse of ``filtered_tab_manager._node_to_where`` /
    ``_leaf_to_where``.

    :param item: Single where-item dict.
    :param report: For warning accumulation.
    :param context_label: Tab label/scope for warning attribution.
    :returns: AST node, or None if the where-item's type is not in
        the schema's leaf-operator vocabulary (caller handles this
        by omitting the whole filter — partial filters are unsafe).
    """
    from espo_impl.core.condition_expression import (
        AllNode, AnyNode, LeafClause, ConditionNode,
    )
    from espo_impl.core.models import OPERATORS  # if needed for the operator vocab check

    if not isinstance(item, dict):
        return None

    item_type = item.get("type")
    if not isinstance(item_type, str):
        return None

    # Compound groups
    if item_type == "and":
        children_data = item.get("value", [])
        children: list[ConditionNode] = []
        for child in children_data if isinstance(children_data, list) else []:
            child_node = self._reverse_where_item(child, report, context_label)
            if child_node is None:
                return None  # whole compound is poisoned by unknown child
            children.append(child_node)
        return AllNode(children=children)
    if item_type == "or":
        children_data = item.get("value", [])
        children: list[ConditionNode] = []
        for child in children_data if isinstance(children_data, list) else []:
            child_node = self._reverse_where_item(child, report, context_label)
            if child_node is None:
                return None
            children.append(child_node)
        return AnyNode(children=children)

    # $user sentinels
    attribute = item.get("attribute")
    if not isinstance(attribute, str) or not attribute:
        return None
    if item_type == "currentUser":
        return LeafClause(field=attribute, op="equals", value="$user")
    if item_type == "notCurrentUser":
        return LeafClause(field=attribute, op="notEquals", value="$user")

    # Nullity (no value)
    if item_type in ("isNull", "isNotNull"):
        return LeafClause(field=attribute, op=item_type)

    # Recognized leaf operators (use the schema's known operator vocab)
    # If type is not in this set, treat as unknown and trigger the
    # outer skip-with-warning behavior
    known_ops = {
        "equals", "notEquals",
        "greaterThan", "greaterThanOrEquals",
        "lessThan", "lessThanOrEquals",
        "in", "notIn", "contains",
    }
    if item_type not in known_ops:
        report.warnings.append(
            f"Filtered tab '{context_label}': unknown where-item "
            f"type '{item_type}' on attribute '{attribute}'"
        )
        return None

    value = item.get("value")
    return LeafClause(field=attribute, op=item_type, value=value)
```

(If `OPERATORS` exists as a constant in `models.py` or
`condition_expression.py`, use it instead of the inline
`known_ops` set; check during implementation.)

**Wire into `run_audit`.** Between Step 3 (relationships) and
Step 3.5 (security from Prompt H):

```python
# Step 3.4: Discover filtered tabs (per DEC-180 default True)
if self._options.include_filtered_tabs:
    self._cb("[AUDIT]    Discovering filtered tabs ...", "cyan")
    self._discover_filtered_tabs(entities, report)
    total_tabs = sum(len(e.filtered_tabs) for e in entities)
    self._cb(
        f"[AUDIT]    Found {total_tabs} filtered tabs across "
        f"{sum(1 for e in entities if e.filtered_tabs)} entities",
        "cyan",
    )
```

**Extend YAML emission.** In `_write_yaml_files`, when writing a
per-entity YAML, include the `filteredTabs:` block when
`entity.filtered_tabs` is non-empty. Each entry serializes:

```python
{
    "id": tab.id,
    "scope": tab.scope,
    "label": tab.label,
    "acl": tab.acl,
    "filter": (
        self._render_filter_ast(tab.filter)
        if tab.filter is not None
        else None
    ),
}
```

The `_render_filter_ast` helper calls
`condition_expression.render_condition(tab.filter)` — the
canonical renderer from Prompt F. If `filter` is None, the YAML
block carries the other fields without a `filter:` key; operators
hand-write the missing filter post-import.

### 2. `automation/db/migrations.py` — `_client_v16`

Mirror `_client_v15` shape. Add after `_client_v15`:

```python
def _client_v16(conn: sqlite3.Connection) -> None:
    """Add FilteredTab table for audit-v1.2 filtered-tab capture.

    Tables hold the audited filtered-tab records per (instance,
    entity) pair. The filter AST is stored as JSON; downstream
    consumers parse it back when needed.

    Idempotent via ``CREATE TABLE IF NOT EXISTS``. Skips silently
    if the Instance table does not yet exist.

    See PRDs/product/crmbuilder-automation-PRD/CLAUDE-CODE-PROMPT-audit-v1.2-I-filtered-tab-audit.md.
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "Instance" not in tables:
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS FilteredTab (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id INTEGER NOT NULL,
            entity_yaml_name TEXT NOT NULL,
            tab_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            label TEXT NOT NULL,
            acl TEXT NOT NULL,
            filter_json TEXT,
            nav_order INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (instance_id) REFERENCES Instance(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_filtered_tab_instance "
        "ON FilteredTab(instance_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_filtered_tab_entity "
        "ON FilteredTab(instance_id, entity_yaml_name)"
    )
```

Append to `CLIENT_MIGRATIONS`:

```python
CLIENT_MIGRATIONS: list[tuple[int, Migration]] = [
    # ... existing entries through (15, _client_v15) ...
    (16, _client_v16),
]
```

### 3. `espo_impl/core/audit_db.py` — filtered-tab insertion

Add `_insert_filtered_tab` mirroring the `_insert_team` /
`_insert_role` shape from Prompt H. The filter AST serializes via
`condition_expression.render_condition()` to a dict, then via
`json.dumps()` to the `filter_json` column.

Wire into `insert_audit_records` after the per-entity insertions
(so the entity's foreign-key target exists). Per-tab insert
contributes to the return count.

### 4. Tests

**`tests/test_audit_manager.py`:**

- `test_discover_filtered_tabs_no_tab_scopes` — server has no
  custom tab-scopes; method returns without API calls beyond
  `get_all_scopes`; no entity gets filtered tabs
- `test_discover_filtered_tabs_one_tab_one_entity` — single tab
  scope binding to Engagement; reverse-translation produces a
  FilteredTabAuditResult with correct id, scope, label, filter
- `test_discover_filtered_tabs_advanced_pack_absent` —
  `list_report_filters` returns 404; method logs informational
  note and continues; no error recorded
- `test_discover_filtered_tabs_report_filter_missing` — binding
  exists in clientDefs but no Report Filter matches the ID;
  warning recorded; entity gets no tab for that scope
- `test_discover_filtered_tabs_unknown_where_type` — Report
  Filter has a where-item with unknown type
  (e.g., `currentQuarter`); warning recorded; tab captured WITH
  label and scope but `filter` is None
- `test_reverse_where_item_currentUser` — `{type:
  "currentUser", attribute: "assignedUser"}` → LeafClause(field=
  "assignedUser", op="equals", value="$user")
- `test_reverse_where_item_isNull` — `{type: "isNull",
  attribute: "X"}` → LeafClause(field="X", op="isNull") with no
  value
- `test_reverse_where_item_and_compound` — `{type: "and",
  value: [<leaf>, <leaf>]}` → AllNode with two children
- `test_reverse_where_item_nested_compound` — nested and/or
  groups reverse correctly
- `test_reverse_where_items_single_leaf_top_level` — top-level
  `[<single leaf>]` → unwrapped to a single LeafClause (not
  wrapped in AllNode)
- `test_reverse_where_items_multi_leaf_top_level` — top-level
  `[<leaf>, <leaf>]` → implicit AllNode with two children
- `test_run_audit_writes_filteredTabs_block_in_entity_yaml` —
  full run with filtered tabs; per-entity YAML output contains a
  `filteredTabs:` block with the captured tabs
- `test_run_audit_no_filteredTabs_when_disabled` —
  `include_filtered_tabs=False`; no discovery API calls; no
  YAML block

**`tests/test_audit_db.py`:**

- `test_insert_filtered_tab_creates_row` —
  FilteredTabAuditResult inserted; row visible with correct
  values; filter_json holds the serialized filter
- `test_insert_filtered_tab_with_none_filter` — tab with
  `filter=None`; filter_json column is NULL
- `test_insert_audit_records_includes_filtered_tab_count` — full
  flow with tabs; return count reflects the inserts

**`tests/db/test_client_migrations.py`:**

- `test_client_v16_creates_filtered_tab_table`
- `test_client_v16_idempotent`
- `test_client_v16_no_instance_table_skips`

## Acceptance Criteria

1. `AuditOptions.include_filtered_tabs` exists and defaults to
   True per DEC-180.
2. `FilteredTabAuditResult` dataclass carries the field shape
   specified in §1.
3. `EntityAuditResult.filtered_tabs` collection exists.
4. `_discover_filtered_tabs` orchestrates the three-step discovery
   (scopes → clientDefs → Report Filters) and gracefully handles
   the HTTP 404 / Advanced-Pack-absent case.
5. `_reverse_where_items` and `_reverse_where_item` correctly
   handle all six where-item variants (compound and/or, currentUser/
   notCurrentUser, isNull/isNotNull, standard leaf operators).
6. Unknown where-item types result in the entire filter being
   omitted (None) with a warning; the tab is still captured with
   label and scope.
7. Per-entity YAML output includes the `filteredTabs:` block when
   `entity.filtered_tabs` is non-empty, rendered via the canonical
   `render_condition` from `condition_expression`.
8. `_client_v16` migration creates the FilteredTab table
   idempotently; registered in `CLIENT_MIGRATIONS`.
9. `audit_db._insert_filtered_tab` inserts records correctly and
   contributes to the `insert_audit_records` total count.
10. All existing tests continue to pass.
11. New tests cover every path enumerated in §4 above.
12. `uv run ruff check espo_impl/ automation/db/ tests/` passes
    clean on touched files.
13. `uv run pytest tests/ -v` passes.
14. Commit and push to `main` with a clear message referencing
    this prompt.

## Out of Scope

- Schema-doc edits — none needed; the v1.1 `filteredTabs:` shape
  is the target
- UI changes — Prompt J
- Documentation updates — Prompt K
- Reverse-engineering of relative-date tokens — operators edit
  manually
- Top-level filter forms not used by `filtered_tab_manager`
  (e.g., raw value dicts at the root) — none are produced by the
  v1.1 deploy half, so audit doesn't need to recognize them

## Reporting Back

When finished, report:

- Modified file paths and line counts
- New tests added (count and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompt J

The expected next step after Prompt I is green is **Prompt J** —
the audit-dialog UI work in
`crmbuilder/automation/ui/deployment/audit_entry.py`. Concretely:
the entity-picker `QListWidget` with pre-flight discovery, the
Security and Filtered tabs checkboxes (defaults checked per
DEC-180), and the overwrite-confirmation dialog (per DEC-181). UI
work, no new domain logic — should be a smaller prompt than I or H.
