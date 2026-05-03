# Claude Code Prompt — Layout list-comparator name/width check

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Bug fix (single prompt; follow-up to commit `3b3e9dc`)

---

## 1. Problem statement

After commit `3b3e9dc` fixed the c-prefix logic in `LayoutManager`,
the **detail** layout for custom entities renders correctly, but
the **list** layout still shows the pre-fix c-prefixed column
names.

Live evidence from the CBM test instance after re-running
Configure on `FU-Contribution.yaml`:

- The Configure log reports
  `[LAYOUT]  Contribution.list ... MATCHES`,
  `[LAYOUT]  Contribution.list ... NO CHANGES NEEDED`.
- Yet `Administration → Entity Manager → Contribution → Layouts → List`
  still has the pre-fix columns enabled:
  `cContributionType`, `cStatus`, `cAmount`, `cReceivedDate`,
  `cAcknowledgmentSent`. The natural-name versions sit in the
  Disabled column unused.

The writer (post-fix) generates a payload with natural names; the
server holds c-prefixed names from before the fix; yet the
comparator reports a structural match and the writer is never
invoked. Detail layouts on the same entity were correctly updated
on the same Configure run.

## 2. Root cause

`espo_impl/core/layout_manager.py`, `_layouts_match` static method
(lines 557–608).

The comparator iterates dict items in `desired` and `current`, and
for each pair checks only:

- `customLabel`
- `rows` (length, then per-row cell `name` for items where rows
  is a list of cell dicts)
- `tabBreak`
- `tabLabel`

For a **detail** layout, each item is a panel dict with
`customLabel` and `rows`, so the comparator reaches into the row
cells and compares the cell `name` values. Mismatches surface and
the writer fires.

For a **list** layout, each item is a flat column dict shaped like
`{"name": "amount", "width": 20}`. There is no `rows` key
(`d_item.get("rows", [])` returns `[]` on both sides), no
`customLabel`, no `tabBreak`, no `tabLabel`. The loop body inspects
none of the keys that actually carry the column identity, finds
no differences in the keys it does inspect, and the comparator
returns `True` for any pair of list payloads of equal length.

In other words: the list-layout comparator is structurally blind
to column field names and widths. Any list payload of the right
length matches any other list payload of the same length.

## 3. Fix

Add per-item comparison of the two keys that list-layout columns
actually carry: `name` and `width`. The change goes inside the
existing `if isinstance(d_item, dict) and isinstance(c_item, dict)`
branch in `_layouts_match`.

Detail-layout panel dicts do not carry a top-level `name` or
`width` key, so on those items both sides return `None` from
`.get(...)` and the new checks are no-ops. The fix is purely
additive — no existing behaviour changes for detail comparisons.

## 4. Required code changes

### 4.1 `espo_impl/core/layout_manager.py`

In `_layouts_match` (currently around line 557), insert two new
checks at the start of the dict-vs-dict branch, before the existing
`customLabel` check.

Replace:

```python
        for d_item, c_item in zip(desired, current, strict=True):
            if isinstance(d_item, dict) and isinstance(c_item, dict):
                # Compare panel: check customLabel and rows
                if d_item.get("customLabel") != c_item.get("customLabel"):
                    return False
```

with:

```python
        for d_item, c_item in zip(desired, current, strict=True):
            if isinstance(d_item, dict) and isinstance(c_item, dict):
                # List-layout columns are flat dicts shaped like
                # {"name": "amount", "width": 20} with no rows or
                # customLabel — they must be compared on `name` and
                # `width` directly. Detail-layout panel dicts do not
                # carry these keys at the top level, so for those
                # items both sides return None and these checks are
                # no-ops.
                if d_item.get("name") != c_item.get("name"):
                    return False
                if d_item.get("width") != c_item.get("width"):
                    return False
                # Compare panel: check customLabel and rows
                if d_item.get("customLabel") != c_item.get("customLabel"):
                    return False
```

No other changes to `_layouts_match`. No changes to any other
method.

## 5. Required test changes

### 5.1 `tests/test_layout_manager.py`

Add the following tests at the end of the file. The first three
exercise `_layouts_match` directly to lock in the comparator
contract; the fourth is an end-to-end test that proves the
comparator fix unblocks the writer for a custom-entity list
layout previously stuck on c-prefixed names.

```python
# --- List-layout comparator tests ---


def test_layouts_match_list_detects_different_names():
    """Two list payloads with different column names must not match.

    Pre-fix, the comparator only inspected customLabel/rows/
    tabBreak/tabLabel — none of which exist on flat list-column
    dicts — so any list payloads of equal length compared as
    matching. This test guards against that regression.
    """
    desired = [{"name": "amount", "width": 20}]
    current = [{"name": "cAmount", "width": 20}]
    assert LayoutManager._layouts_match(desired, current) is False


def test_layouts_match_list_detects_different_widths():
    """Two list payloads with same names but different widths must
    not match."""
    desired = [{"name": "amount", "width": 20}]
    current = [{"name": "amount", "width": 30}]
    assert LayoutManager._layouts_match(desired, current) is False


def test_layouts_match_list_identical_payloads_match():
    """Two structurally identical list payloads must match."""
    desired = [
        {"name": "name", "width": 30},
        {"name": "amount", "width": 20},
        {"name": "status"},
    ]
    current = [
        {"name": "name", "width": 30},
        {"name": "amount", "width": 20},
        {"name": "status"},
    ]
    assert LayoutManager._layouts_match(desired, current) is True


def test_custom_entity_list_layout_overwrites_stale_c_prefixed_state():
    """When a custom entity's list layout on the server still has
    pre-fix c-prefixed column names, Configure must detect the
    mismatch against the natural-name desired payload and overwrite.
    """
    client = MagicMock(spec=EspoAdminClient)
    # Simulate the broken pre-fix state on the server.
    client.get_layout.return_value = (
        200,
        [
            {"name": "name", "width": 30},
            {"name": "cAmount", "width": 20},
            {"name": "cStatus", "width": 20},
        ],
    )
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
            ("status", "enum", "ident"),
        ),
        layouts={
            "list": LayoutSpec(
                layout_type="list",
                columns=[
                    ColumnSpec(field="name", width=30),
                    ColumnSpec(field="amount", width=20),
                    ColumnSpec(field="status", width=20),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    # Comparator must have detected the mismatch — writer must run.
    assert client.save_layout.call_count == 1
    saved_payload = client.save_layout.call_args.args[2]
    assert saved_payload == [
        {"name": "name", "width": 30},
        {"name": "amount", "width": 20},
        {"name": "status", "width": 20},
    ]
```

## 6. Out of scope

- Do NOT touch the writer logic. The writer was already correct
  after `3b3e9dc`; this prompt fixes only the comparator that was
  short-circuiting the writer for list layouts.
- Do NOT add comparison of other column attributes (e.g. `link`,
  `notSortable`, `align`). The current `ColumnSpec` model only
  carries `field` and `width`, so the writer never produces those
  keys. Adding speculative comparisons risks false-mismatches if
  EspoCRM returns server-side defaults the writer doesn't author.
  Reopen this if/when `ColumnSpec` grows.
- Do NOT modify any YAML files.

## 7. Verification steps

1. **Unit tests:** `uv run pytest tests/test_layout_manager.py -v`.
   All previously passing tests must still pass; the four new
   tests must pass.
2. **Lint:** `uv run ruff check espo_impl/ tests/test_layout_manager.py`.
3. **End-to-end (manual, run by Doug):** Re-run Configure on
   `FU-Contribution.yaml` against the live CBM instance. The log
   should now read:

   ```
   [LAYOUT]  Contribution.detail ... MATCHES        (already correct, no-op)
   [LAYOUT]  Contribution.list ... CHECKING
   [LAYOUT]  Contribution.list ... APPLYING
   [LAYOUT]  Contribution.list ... UPDATED OK
   ```

   Then open
   `Administration → Entity Manager → Contribution → Layouts → List`
   and confirm the Enabled column shows non-prefixed names
   (`name`, `amount`, `status`, ...) instead of `cAmount`,
   `cStatus`, etc.

## 8. Commit

Single commit, message:

```
fix(layout): compare name and width on list-layout columns

After 3b3e9dc fixed the writer to skip c-prefix on custom-entity
layouts, the detail layout for Contribution rendered correctly,
but the list layout continued to show the pre-fix c-prefixed
columns. Configure logged 'Contribution.list ... MATCHES' on
every run, never invoking the writer.

The cause was in _layouts_match. For each pair of dict items it
inspected only customLabel, rows, tabBreak, and tabLabel. Detail
panels carry rows, which contain cell dicts whose `name` values
the comparator does inspect — so detail mismatches surfaced
correctly. List columns are flat dicts shaped like
{"name": "amount", "width": 20} with none of the four inspected
keys; the comparator iterated through them, found nothing to
disagree on, and returned True for any list payloads of equal
length.

Fix: add per-item `name` and `width` checks at the start of the
dict-vs-dict branch in _layouts_match. Detail panel dicts do not
carry these keys at the top level, so the new checks are no-ops
for detail comparisons. List columns now compare on the keys
they actually carry, and the writer fires whenever names or
widths drift.

Adds three direct comparator tests (different names, different
widths, identical match) and one end-to-end test simulating a
server with pre-fix c-prefixed list columns to prove the writer
is now invoked.
```
