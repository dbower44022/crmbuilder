# CLAUDE-CODE-PROMPT-v2-ui-v0.2-D-topics-and-tree-picker

**Last Updated:** 05-08-26
**Series:** v2-ui-v0.2
**Slice:** D (4 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.2-C (planning items CRUD)

## Purpose

Slice D delivers the Topics CRUD surface, the QTreeView master panel swap, and the activation of the `HierarchicalEntityPicker` widget (built in slice A) for the parent_topic field. Topics is the most structurally novel of the three CRUD entities in v0.2 because of the hierarchical parent_topic relationship.

After this slice:

- The Topics master panel renders as a `QTreeView` backed by a `QStandardItemModel` (replacing v0.1's flat `QTableView` with name-prefix indentation). Roots are top-level topics; children nest under parents via `parent_topic_id`. Single-row selection updates the detail pane.
- A "New Topic" button opens a Create dialog. Edit and Delete buttons appear on the Topics detail pane.
- The Topic create/edit dialog's `parent_topic` field is a tree picker (the `HierarchicalEntityPicker` widget from slice A), with cycle filtering — on Edit, the topic itself and its descendants are non-selectable.
- The `ReferencesSection` widget renders on the Topics detail pane.
- Re-parenting works through the dialog's parent_topic field.

## Project context

Slice A delivered `HierarchicalEntityPicker` as a reusable widget but did not wire any consumer to it. Slice D is the first user. The widget's constructor accepts a list of `Node` objects (id, label, parent_id) and an optional `selectable` predicate callback that returns False for nodes that should be non-selectable. Topics-specific cycle filtering: on Edit, the predicate returns False for the topic being edited and any of its descendants (computed by walking the tree from the edited topic's id).

The `EntityCrudDialog` field schema (from slice A) supports `widget="tree_picker"`. When the base class encounters this widget type, it instantiates `HierarchicalEntityPicker` on click, passing the schema's `tree_picker_data(client)` callback to fetch nodes and (on Edit) the schema's `tree_picker_filter(client, record)` callback to compute the selectable predicate. The schema declares the callbacks as functions that take the storage client (and optionally the record being edited) and return the list of nodes / the predicate.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity: `Doug <doug@dougbower.com>`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice C is on `main`.
6. Confirm the v2 test suite passes.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md` — section 4.4 (Topics CRUD with hierarchical UX).
3. `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md` — Step D in section 4.
4. Slice A's deliverables:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/hierarchical_picker.py` — the picker widget.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py` — `FieldSchema` `tree_picker_data` / `tree_picker_filter` callbacks; `EntityCrudDialog`'s tree_picker handling.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py`.
5. Slices B/C deliverables (for the per-entity dialog/panel pattern):
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/risk_create.py`, `planning_item_create.py`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/risks.py`, `planning_items.py`.
6. Existing Topics surface:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/topics.py` — currently flat-with-indentation `QTableView`. Slice D rewrites the master pane.
   - `crmbuilder-v2/src/crmbuilder_v2/access/models.py` — Topic SQLAlchemy model (note `parent_topic_id` FK).
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/topics.py`.
   - `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` — Topic schemas.
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/topics.py`.
7. **Tier 2 orientation**: current charter, current status, SES-006, DEC-007 (Topics table — original design), DEC-030 (slice D's design rationale), DEC-031 (ReferencesSection generalization).

## Step 1 — Discover the Topic field set

Read the Topic model and Pydantic schema. Expected field set:

- `identifier` — text, required, format pattern (verify; likely `TOP-NNN`).
- `name` — text, required.
- `description` — multi-line text.
- `parent_topic` — tree_picker, optional. The schema's `tree_picker_data` callback fetches all topics; on Edit, `tree_picker_filter` builds a predicate that excludes the current topic and its descendants.

If the model has additional fields, include them. If the schema accepts a `parent_topic_identifier` rather than `parent_topic` as the API field name, use the API name in the FieldSchema's `key`.

If the storage system does not currently expose `POST /topics`, `PATCH /topics/{id}`, or `DELETE /topics/{id}`, add them per the slice B/C pattern.

## Step 2 — Extend `StorageClient` with topic write methods

```python
def create_topic(self, body: dict) -> dict:
    return self._request("POST", "/topics", json=body)


def update_topic(self, identifier: str, body: dict) -> dict:
    return self._request("PATCH", f"/topics/{identifier}", json=body)


def delete_topic(self, identifier: str) -> dict:
    return self._request("DELETE", f"/topics/{identifier}")
```

Confirm `list_topics` and `get_topic` exist from v0.1 (they should — Topics was a v0.1 read-only panel).

## Step 3 — Define the Topic dialog classes

### `dialogs/topic_create.py` (new)

```python
"""Topics Create dialog. Per ui-PRD-v0.2.md §4.4."""
import re

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog, FieldSchema
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.widgets.hierarchical_picker import HierarchicalEntityPicker


def _fetch_topic_nodes(client: StorageClient) -> list[HierarchicalEntityPicker.Node]:
    """Build the picker node list from all topics."""
    topics = client.list_topics()
    return [
        HierarchicalEntityPicker.Node(
            id=t["identifier"],
            label=f"{t['identifier']} — {t['name']}",
            parent_id=t.get("parent_topic_identifier"),
        )
        for t in topics
    ]


def _no_filter(node: HierarchicalEntityPicker.Node) -> bool:
    """Create-mode: every node is selectable. No cycle to prevent."""
    return True


_TOPIC_FIELDS_CREATE: list[FieldSchema] = [
    FieldSchema(
        key="identifier", label="Identifier", widget="line",
        required=True, placeholder="TOP-NNN",
        regex=re.compile(r"^TOP-\d{3,}$"),  # verify the convention
    ),
    FieldSchema(key="name", label="Name", widget="line", required=True),
    FieldSchema(key="description", label="Description", widget="text"),
    FieldSchema(
        key="parent_topic", label="Parent Topic", widget="tree_picker",
        tree_picker_data=lambda client: _fetch_topic_nodes(client),
        tree_picker_filter=lambda client, record: _no_filter,
    ),
]


class TopicCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            _TOPIC_FIELDS_CREATE,
            mode="create",
            title="New Topic",
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        return self.saved_identifier()
```

### `dialogs/topic_edit.py` (new)

```python
def _exclude_self_and_descendants(client: StorageClient, record: dict) -> Callable[[Node], bool]:
    """Edit-mode: build a predicate that returns False for the topic
    being edited and all of its descendants."""
    edited_id = record["identifier"]
    topics = client.list_topics()
    children: dict[str, list[str]] = {}
    for t in topics:
        parent = t.get("parent_topic_identifier")
        if parent:
            children.setdefault(parent, []).append(t["identifier"])

    excluded: set[str] = set()
    stack = [edited_id]
    while stack:
        node_id = stack.pop()
        if node_id in excluded:
            continue
        excluded.add(node_id)
        stack.extend(children.get(node_id, []))

    def predicate(node: HierarchicalEntityPicker.Node) -> bool:
        return node.id not in excluded

    return predicate


def _topic_fields_edit() -> list[FieldSchema]:
    """Edit-mode: identifier read-only, parent picker uses
    cycle-prevention filter."""
    fields = [dataclasses.replace(f) for f in _TOPIC_FIELDS_CREATE]
    fields[0].read_only = True  # identifier
    # Replace the parent_topic field's filter callback.
    parent_field = next(f for f in fields if f.key == "parent_topic")
    parent_field.tree_picker_filter = lambda client, record: _exclude_self_and_descendants(client, record)
    return fields


class TopicEditDialog(EntityCrudDialog):
    def __init__(
        self,
        client: StorageClient,
        record: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            _topic_fields_edit(),
            mode="edit",
            title=f"Edit {record['identifier']}",
            record=record,
            parent=parent,
        )
```

The pattern of `tree_picker_filter` taking the client and record and returning a predicate keeps the cycle-prevention logic close to the schema declaration.

### `dialogs/topic_delete.py` (new)

```python
class TopicDeleteDialog(EntityCrudDeleteDialog):
    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            identifier,
            title,
            client.delete_topic,
            parent=parent,
        )
```

If a topic has children, the delete needs to either fail with a ConflictError (children must be re-parented or deleted first) or cascade (delete children too). The access layer's behavior governs; the dialog presents whatever the API returns. If ConflictError, the defensive ErrorDialog from `EntityCrudDeleteDialog` surfaces; the user must address the children manually before retrying.

## Step 4 — Switch the Topics master panel to QTreeView

Rewrite `panels/topics.py`'s master pane.

### Model construction

The current panel uses a `QTableView` with `QStandardItemModel` populated as flat rows. Replace with a `QTreeView` populated as a tree:

```python
def _populate_model(self, topics: list[dict]) -> None:
    """Populate the tree model from a flat list of topics."""
    self._model.clear()
    self._model.setHorizontalHeaderLabels(["Topic"])

    # Build parent → children mapping.
    by_parent: dict[str | None, list[dict]] = {}
    for t in topics:
        by_parent.setdefault(t.get("parent_topic_identifier"), []).append(t)

    # Sort each level alphabetically.
    for k in by_parent:
        by_parent[k].sort(key=lambda t: t["name"])

    # Recursive insert from roots.
    def insert_children(parent_item: QStandardItem | None, parent_id: str | None) -> None:
        for t in by_parent.get(parent_id, []):
            item = QStandardItem(f"{t['identifier']} — {t['name']}")
            item.setData(t["identifier"], Qt.UserRole)
            item.setEditable(False)
            if parent_item is None:
                self._model.appendRow(item)
            else:
                parent_item.appendRow(item)
            insert_children(item, t["identifier"])

    insert_children(None, None)

    # Expand all by default; a user can collapse if desired.
    self._tree_view.expandAll()
```

### Selection wiring

```python
self._tree_view.selectionModel().currentChanged.connect(self._on_selection_changed)


def _on_selection_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
    if not current.isValid():
        self.selection_changed.emit(None)
        return
    item = self._model.itemFromIndex(current)
    identifier = item.data(Qt.UserRole)
    self.selection_changed.emit(identifier)
```

The `selection_changed` signal carries the topic identifier (string) and is wired to the existing detail-pane render path. The detail-pane behavior is otherwise unchanged from v0.1.

### Toolbar and detail-pane buttons

Add the New Topic button and Edit/Delete buttons per slice B/C pattern.

### `ReferencesSection` on detail pane

```python
references_section = ReferencesSection(
    self._client,
    "topic",
    record["identifier"],
    parent=self,
)
references_section.navigate_requested.connect(self.navigate_requested)
```

### Slice H Parent Topic cell-click navigation

The v0.1 slice H delivered "Click on Parent Topic cell with value emits navigate_requested." With the QTableView replaced by QTreeView, the cell-click navigation moves to the tree column. Each non-root node already has its parent visible as the parent tree node (the QTreeView shows the hierarchy directly), so cell-click-to-navigate-to-parent is no longer the primary affordance — clicking the parent tree row is. The existing slice H test (`test_topics_hierarchy.py::test_parent_topic_cell_click_navigates`) should be updated to reflect the new shape:

- Single-click on a child row → selects the child (existing behavior; detail pane updates).
- Single-click on the parent tree row → selects the parent.
- The "click on Parent Topic cell" interaction no longer exists because there is no Parent Topic cell column; the parent is the parent node in the tree.

If any v0.1 slice H test was specifically asserting the cell-click semantics, it is replaced with a tree-row-click test that confirms the same end-user behavior (selecting a parent updates the detail pane to that parent's record) via the tree's selection mechanism.

## Step 5 — Tests

### `tests/crmbuilder_v2/ui/test_topic_dialogs.py` (new)

- TopicCreateDialog renders the field set including a tree_picker for parent_topic.
- Selecting a parent in the tree picker populates the parent_topic field with the picker's id.
- TopicEditDialog: cycle prevention — on Edit of TOP-1, descendants of TOP-1 are non-selectable in the picker.
- TopicEditDialog: re-parenting — selecting a different valid parent and saving sends the correct PATCH body.
- TopicDeleteDialog confirmation.
- Successful create / edit / delete; same shape as risks/planning items tests.

### `tests/crmbuilder_v2/ui/test_topics_panel_writes.py` (new — may replace or extend `test_topics_hierarchy.py`)

- Master panel renders as a QTreeView with parent-child nesting.
- Clicking a tree row updates the detail pane.
- Expand/collapse works.
- New Topic button opens create dialog.
- Edit/Delete buttons in detail pane.
- Successful create triggers refresh + select.
- ReferencesSection renders on detail pane.

### Update `tests/crmbuilder_v2/ui/test_topics_hierarchy.py`

If this test file exists from slice H, update its tests to reflect the QTreeView shape. The end-user behavior assertions ("clicking a parent navigates to it") stay; the implementation assertions ("clicking a Parent Topic cell with non-empty value") become tree-row clicks.

## Step 6 — Verify and commit

Run:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: slice A + B + C tests + new tests. Estimated 340+ passing.

Manual verification:

1. **QTreeView master.** Launch UI, navigate to Topics. Confirm the master panel is a tree with parent-child nesting. Click a parent to expand/collapse. Click a child to select; confirm detail pane updates.
2. **Create topic with parent.** Click New Topic; fill identifier/name; click the Parent Topic field button; the picker opens; select an existing topic; click OK; the field shows the chosen parent. Click Save; confirm the new topic appears in the tree under its parent.
3. **Create topic without parent.** Click New Topic; click the Parent Topic button; click "No selection"; confirm the field shows "No parent". Save; confirm the new topic is at the root level.
4. **Edit topic — re-parent.** Select an existing topic; click Edit. The current parent is shown. Click the Parent Topic button; select a different valid parent; OK. Save; confirm the topic moves under the new parent in the tree.
5. **Edit topic — cycle prevention.** Select a topic that has children; click Edit. Click the Parent Topic button; in the picker, confirm the topic itself and its descendants are visually grayed and clicking them does not enable OK.
6. **Delete topic with no children.** Select; Delete; confirm; row disappears.
7. **Delete topic with children.** Select; Delete; confirm. If the access layer rejects with a ConflictError, the ErrorDialog appears explaining why. The user re-parents children first and retries.
8. **References on detail pane.** Verify ReferencesSection renders for a topic with at least one reference.
9. **Watcher integration.** `curl POST /topics` while panel is open; confirm new row appears in the tree.

Commit shape:

```
v2: ui topics CRUD — QTreeView master, hierarchical picker, dialogs

Implements slice D of the v2-ui-v0.2 series. Per ui-PRD-v0.2.md §4.4
and §4.6:

- panels/topics.py: master panel switches from flat QTableView with
  name-prefix indentation to a QTreeView backed by a
  QStandardItemModel. Tree-from-flat-list construction; alphabetical
  within each level; expand-all default. Single-row selection emits
  the existing selection_changed signal so the detail-pane behavior
  is unchanged.

- TopicCreateDialog, TopicEditDialog, TopicDeleteDialog using
  EntityCrudDialog and EntityCrudDeleteDialog. The parent_topic
  field uses widget='tree_picker', which the base instantiates
  HierarchicalEntityPicker for.

- Cycle prevention on Edit: the picker's selectable-predicate
  callback returns False for the topic being edited and all of its
  descendants (computed by walking the parent → children map).
  Re-parenting works for any other valid target.

- ReferencesSection on the Topics detail pane.

- StorageClient extended with create_topic, update_topic, delete_topic.

- Updated test_topics_hierarchy.py for QTreeView shape; new
  test_topic_dialogs.py and test_topics_panel_writes.py.

Out of slice: charter, status, show-deleted (slices E, F).
```

If storage additions were needed:

```
v2: storage adds POST/PATCH/DELETE for topics
```

Push to origin/main.

## Acceptance gates

1. Topics master panel renders as a QTreeView with parent-child nesting. (PRD AC#6.)
2. Clicking a tree row updates the detail pane.
3. New Topic, Edit Topic, Delete Topic flows work end-to-end.
4. Parent picker opens as a modal tree; selecting a node populates the field; "No selection" clears it.
5. Cycle prevention works on Edit.
6. Re-parenting works.
7. ReferencesSection on Topics detail pane.
8. Live refresh works.
9. Test suite passes.
10. Commit(s) on origin/main.

## Out of slice

- Charter, Status, Show-deleted toggle, polish, closeout. Slices E and F.
- Drag-to-reparent on the QTreeView (out of v0.2 entirely; possible v0.3).

## Constraints

- **No new external dependencies.**
- **Storage additions only if needed.**
- **Reuse the schema-driven dialog pattern.**
- **The `HierarchicalEntityPicker` widget is consumed, not modified.** If a behavior tweak is needed, surface it as a base-class change with a clear motivation.
- **Stop and ask if uncertain.**

## Reporting

After execution, produce a completion report covering:

- Acceptance gates pass/fail.
- Files created or modified.
- Field set discovered and Topic identifier convention used.
- Storage additions (if any).
- Test results.
- Manual verification confirmation, including the cycle-prevention scenarios.
- Any base-class friction encountered (suggested polish for slice F).
- What slice E will need.
