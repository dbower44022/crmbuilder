# Claude Code Prompt — Auto-place required `name` field on detail layouts

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Feature (single prompt; supersedes the need for per-YAML manual `name` placement)

---

## 1. Problem statement

EspoCRM treats every entity's system `name` field as required. When
a YAML's `detail:` layout doesn't explicitly place `name` on a
panel, the resulting Configure run produces a detail/edit form with
no `name` input. EspoCRM still demands a value on save, and every
record-creation attempt fails with:

```
Bad request — Backend validation failure.
Field: name, Validation: required
```

Live evidence from CBM: every custom-entity YAML in the
`ClevelandBusinessMentoring` repository expresses its detail
layout as category-driven `tabs:` blocks (`Identification`,
`Lifecycle Dates`, etc.). The system `name` field has no category,
so the tab-expansion logic in `LayoutManager._expand_tabs` never
places it. Examples that exhibit the problem today:
`FU/FU-Contribution.yaml`, `FU/FU-FundraisingCampaign.yaml`,
`MR/MR-Dues.yaml`. Same for any future custom entity authored to
the current pattern.

The list-layout side already works because YAMLs include
`field: name` in `list.columns`. The break is detail-only.

## 2. Design — engine-side auto-placement

`LayoutManager` will guarantee that every panel-style layout
(detail, detailSmall, edit) it writes to EspoCRM contains a `name`
cell. The rule:

1. After `_build_detail_payload` finishes assembling panels from
   YAML, scan every cell across every row of every panel.
2. If a cell whose name resolves to `name` (case-sensitive) is
   already present anywhere in the payload, do nothing — respect
   the YAML's explicit placement.
3. Otherwise, prepend a single-cell row `[{"name": "name"}]` to
   the rows of the **first panel that has no `dynamicLogicVisible`
   attached** (i.e., the first always-visible panel). This
   prevents the required `name` field from being hidden behind a
   conditional.
4. If no panel qualifies (every panel is conditional), prepend the
   row to the very first panel as a fallback. Better to have
   `name` placed conditionally than not at all.
5. If the layout has zero panels, skip auto-placement — that's a
   YAML-shaped problem, not a layout-writer problem.

The behavior is opt-out via a new entity setting
`autoPlaceName: false`. Default is `true`. The opt-out exists for
future entities whose `name` is computed by formula or workflow,
where surfacing a manual input would be wrong.

The rule applies uniformly to native and custom entities. `name`
is required on every entity in EspoCRM regardless.

The rule applies to every layout type that takes panels (detail,
detailSmall, edit, etc.) — i.e., every layout type **other than
`list` and `listSmall`** in the existing
`_build_payload` dispatch.

## 3. Required code changes

### 3.1 `espo_impl/core/models.py`

**Change 1** — extend `EntitySettings`:

Replace:

```python
@dataclass
class EntitySettings:
    """Typed representation of the entity-level ``settings:`` block.

    :param labelSingular: Singular display name for the entity.
    :param labelPlural: Plural display name for the entity.
    :param stream: Whether the activity-feed Stream panel is enabled.
    :param disabled: Whether the entity is disabled in the CRM UI.
    """

    labelSingular: str | None = None
    labelPlural: str | None = None
    stream: bool | None = None
    disabled: bool | None = None
```

with:

```python
@dataclass
class EntitySettings:
    """Typed representation of the entity-level ``settings:`` block.

    :param labelSingular: Singular display name for the entity.
    :param labelPlural: Plural display name for the entity.
    :param stream: Whether the activity-feed Stream panel is enabled.
    :param disabled: Whether the entity is disabled in the CRM UI.
    :param autoPlaceName: Whether LayoutManager auto-prepends the
        required system `name` field to detail/edit layouts when the
        YAML does not explicitly place it. Default True. Set False
        for entities whose `name` is computed via formula or
        workflow and should not surface as a manual input.
    """

    labelSingular: str | None = None
    labelPlural: str | None = None
    stream: bool | None = None
    disabled: bool | None = None
    autoPlaceName: bool | None = None
```

**Change 2** — extend `VALID_SETTINGS_KEYS`:

Replace:

```python
VALID_SETTINGS_KEYS: set[str] = {
    "labelSingular", "labelPlural", "stream", "disabled",
}
```

with:

```python
VALID_SETTINGS_KEYS: set[str] = {
    "labelSingular", "labelPlural", "stream", "disabled",
    "autoPlaceName",
}
```

### 3.2 `espo_impl/core/config_loader.py`

**Change 3** — extend `_parse_settings`:

In the function `_parse_settings` (around line 715), update the
returned `EntitySettings(...)` constructor call to also read
`autoPlaceName`:

Replace:

```python
        return EntitySettings(
            labelSingular=raw.get("labelSingular"),
            labelPlural=raw.get("labelPlural"),
            stream=raw.get("stream"),
            disabled=raw.get("disabled"),
        )
```

with:

```python
        return EntitySettings(
            labelSingular=raw.get("labelSingular"),
            labelPlural=raw.get("labelPlural"),
            stream=raw.get("stream"),
            disabled=raw.get("disabled"),
            autoPlaceName=raw.get("autoPlaceName"),
        )
```

**Change 4** — add type validation alongside the existing
`stream`/`disabled` boolean checks (around line 1715, just after
the `disabled` check):

Insert after the existing `disabled` boolean check:

```python
        auto_place_name_val = entity.settings_raw.get("autoPlaceName")
        if auto_place_name_val is not None and not isinstance(
            auto_place_name_val, bool
        ):
            errors.append(
                f"{entity.name}.settings.autoPlaceName: must be a boolean"
            )
```

### 3.3 `espo_impl/core/layout_manager.py`

**Change 5** — thread the `auto_place_name` flag from
`process_layouts` down to `_build_detail_payload`. Three signatures
extend; `_build_payload` and `_process_one_layout` take a new
`auto_place_name: bool` parameter; they pass it through.

In `process_layouts` (around line 56), after building
`custom_field_names`, derive the flag:

```python
        # Default True. Entity-level setting can opt out (e.g. when
        # `name` is supplied by a formula or workflow).
        auto_place_name = True
        if entity_def.settings is not None:
            if entity_def.settings.autoPlaceName is False:
                auto_place_name = False
```

Pass `auto_place_name` into the existing call to
`self._process_one_layout(...)` as a new keyword argument.

Update `_process_one_layout` signature to accept
`auto_place_name: bool`, and forward it into the call to
`self._build_payload(...)`.

Update `_build_payload` signature to accept `auto_place_name: bool`.
For the `list` branch the flag is unused — name placement is YAML-
expressed for list columns. For the non-list branch, forward the
flag into `self._build_detail_payload(...)`.

Update `_build_detail_payload` signature to accept
`auto_place_name: bool`. After the existing `for panel in
layout_spec.panels or []` loop has finished assembling `result`,
call the new helper:

```python
        if auto_place_name:
            self._ensure_name_placed(result, custom_field_names)

        return result
```

**Change 6** — add the new helper method on `LayoutManager`. Place
it directly above `_layouts_match` so the helper sits with the
other panel-shaping methods. The helper resolves the API name for
`name` (which on native entities would be c-prefixed if `name`
were custom — it isn't, so resolution returns `"name"` either way,
but keep the call for symmetry with the rest of the code):

```python
    def _ensure_name_placed(
        self,
        panels: list[dict[str, Any]],
        custom_field_names: set[str],
    ) -> None:
        """Prepend a `name` row to the first always-visible panel
        if `name` is not already placed somewhere in the layout.

        EspoCRM treats `name` as required on every entity. YAMLs
        that express their detail layout via category-driven `tabs:`
        blocks routinely fail to place `name` (it has no category),
        producing a create form on which the user cannot enter the
        required value. This helper guarantees `name` lands on the
        layout.

        Mutates `panels` in place. No-op when:
            - `panels` is empty (YAML-shape problem, not ours);
            - any cell anywhere in `panels` already resolves to
              `name`.

        :param panels: Built detail-layout panel list.
        :param custom_field_names: Set of custom field names (for
            symmetry with the rest of the layout code; `name` is
            always native and resolves to itself).
        """
        if not panels:
            return

        target_name = self._resolve_field_name("name", custom_field_names)

        # Detect existing placement.
        for panel in panels:
            for row in panel.get("rows") or []:
                if not isinstance(row, list):
                    continue
                for cell in row:
                    cell_name = (
                        cell.get("name")
                        if isinstance(cell, dict)
                        else cell
                    )
                    if cell_name == target_name:
                        return

        # Pick insertion target: first panel without
        # `dynamicLogicVisible`. Fall back to first panel.
        target = next(
            (p for p in panels if not p.get("dynamicLogicVisible")),
            panels[0],
        )
        existing_rows = target.get("rows") or []
        target["rows"] = [[{"name": target_name}], *existing_rows]
```

No other layout_manager changes.

### 3.4 `tests/test_layout_manager.py`

Add the following tests at the end of the file. They cover the
five behavioral commitments above.

```python
# --- Auto-placement of `name` on detail layouts ---


def _process_with_settings_for_name(client, entity_settings):
    """Helper: build a Contribution-like custom entity with a
    detail layout that does NOT place `name`, optionally with the
    given EntitySettings, and run process_layouts."""
    from espo_impl.core.models import EntitySettings

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
            ("status", "enum", "ident"),
        ),
        settings=entity_settings,
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Identification",
                        rows=[["amount", "status"]],
                    ),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)
    _ = EntitySettings  # silence linter on the import-only line
    return client


def test_auto_place_name_default_true_prepends_name():
    """When the YAML does not place `name`, the engine prepends a
    name row to the first panel by default."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    _process_with_settings_for_name(client, entity_settings=None)

    saved_payload = client.save_layout.call_args.args[2]
    assert saved_payload[0]["rows"][0] == [{"name": "name"}]
    # original row preserved as second row
    assert saved_payload[0]["rows"][1] == [
        {"name": "amount"},
        {"name": "status"},
    ]


def test_auto_place_name_explicit_placement_not_duplicated():
    """When the YAML already places `name` somewhere, the engine
    does not add another."""
    from espo_impl.core.models import EntitySettings

    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(("amount", "currency", "ident")),
        settings=None,
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Identification",
                        rows=[["name"], ["amount"]],
                    ),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)
    _ = EntitySettings

    saved_payload = client.save_layout.call_args.args[2]
    # Panel still has exactly the two YAML-authored rows.
    assert saved_payload[0]["rows"] == [
        [{"name": "name"}],
        [{"name": "amount"}],
    ]


def test_auto_place_name_opt_out_skips_placement():
    """settings.autoPlaceName=False suppresses auto-placement."""
    from espo_impl.core.models import EntitySettings

    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    _process_with_settings_for_name(
        client, entity_settings=EntitySettings(autoPlaceName=False)
    )

    saved_payload = client.save_layout.call_args.args[2]
    # Only the YAML-authored row remains.
    assert saved_payload[0]["rows"] == [
        [{"name": "amount"}, {"name": "status"}]
    ]


def test_auto_place_name_skips_conditional_panel():
    """When the first panel has dynamicLogicVisible, name is
    prepended to the first always-visible panel instead."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
            ("nextGrantDeadline", "date", "grant"),
        ),
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Grant Details",
                        rows=[["nextGrantDeadline"]],
                        dynamicLogicVisible={
                            "attribute": "contributionType",
                            "value": "Grant",
                        },
                    ),
                    PanelSpec(
                        label="Identification",
                        rows=[["amount"]],
                    ),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    # Panel index 0 (conditional) is untouched.
    assert saved_payload[0]["rows"] == [[{"name": "nextGrantDeadline"}]]
    # Panel index 1 (always-visible) has name prepended.
    assert saved_payload[1]["rows"][0] == [{"name": "name"}]
    assert saved_payload[1]["rows"][1] == [{"name": "amount"}]


def test_auto_place_name_all_panels_conditional_falls_back_to_first():
    """When every panel is conditional, fall back to the first
    panel rather than skipping placement entirely."""
    client = MagicMock(spec=EspoAdminClient)
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    manager, _ = make_manager(client)
    entity = EntityDefinition(
        name="Contribution",
        fields=make_fields(
            ("amount", "currency", "ident"),
        ),
        layouts={
            "detail": LayoutSpec(
                layout_type="detail",
                panels=[
                    PanelSpec(
                        label="Conditional",
                        rows=[["amount"]],
                        dynamicLogicVisible={
                            "attribute": "contributionType",
                            "value": "Grant",
                        },
                    ),
                ],
            )
        },
    )
    manager.process_layouts(entity, entity.fields)

    saved_payload = client.save_layout.call_args.args[2]
    # Better placed conditionally than not at all.
    assert saved_payload[0]["rows"][0] == [{"name": "name"}]
    assert saved_payload[0]["rows"][1] == [{"name": "amount"}]
```

### 3.5 `PRDs/product/app-yaml-schema.md`

**Change 7** — document the new setting in Section 5.4.

In the settings table (currently 4 rows, after the `disabled` row),
append:

```markdown
| `autoPlaceName` | boolean | no | When `true` (default), `LayoutManager` auto-prepends the required system `name` field to detail/edit layouts that do not explicitly place it. Set to `false` for entities whose `name` is computed by formula or workflow and should not surface as a manual input. |
```

After the table, append a new short paragraph:

```markdown
**`autoPlaceName` rationale.** EspoCRM treats `name` as required on
every entity. YAMLs that build detail layouts from category-driven
`tabs:` blocks routinely fail to place `name` (it has no category),
producing a create form on which users cannot enter the required
value. The default `true` behavior shields YAML authors from this
trap. Place `name` explicitly anywhere in `detail.panels` if you
want it in a specific row or panel — the engine respects explicit
placement and does not duplicate. Set `autoPlaceName: false` only
when `name` is supplied by a formula or workflow.
```

Also bump the document's "Last Updated" date in the revision
control section to today's date in `MM-DD-YY HH:MM` format, and
add a row to the change-log table:

```markdown
| <bumped version> | <today MM-DD-YY HH:MM> | Adds `settings.autoPlaceName` (default `true`); LayoutManager now auto-prepends the system `name` field to detail/edit layouts unless explicitly placed or opted out. |
```

(Use the next minor version after the current one in the change-log
table.)

## 4. Out of scope

- Do NOT modify any YAML files in `ClevelandBusinessMentoring`.
  The next Configure run against each entity will pick up the
  auto-placement automatically — the comparator already detects
  the new `name` row in the desired payload, sees it's missing
  from the server's current layout, and triggers a write. No
  manual YAML edits required.
- Do NOT add a `validate_program()` warning for opt-out cases —
  whether to surface `name` is a deliberate choice when
  `autoPlaceName: false` is set, and warning would be noisy.
- Do NOT touch the list-layout path. List columns already include
  `name` explicitly per YAML and don't need engine help.
- Do NOT change `_resolve_field_name`, `_layouts_match`, or the
  c-prefix gating from commits `3b3e9dc` / `1115527`.

## 5. Verification steps

1. **Unit tests:** `uv run pytest tests/test_layout_manager.py -v`.
   All previously passing tests must still pass; the five new
   tests must pass.
2. **Settings tests:** `uv run pytest tests/test_config_loader.py -v`
   if a relevant test file exists. Add a test asserting that
   `settings.autoPlaceName: "yes"` (non-bool) produces a validation
   error matching the new check; the existing tests for
   `stream`/`disabled` are the model.
3. **Lint:** `uv run ruff check espo_impl/ tests/`.
4. **End-to-end (manual, run by Doug):** Re-run Configure on
   `FU-Contribution.yaml` against the live CBM instance. Expected
   log fragment:

   ```
   [LAYOUT]  Contribution.detail ... CHECKING
   [LAYOUT]  Contribution.detail ... APPLYING
   [LAYOUT]  Contribution.detail ... UPDATED OK
   [LAYOUT]  Contribution.list ... CHECKING
   [LAYOUT]  Contribution.list ... MATCHES
   [LAYOUT]  Contribution.list ... NO CHANGES NEEDED
   ```

   Then in EspoCRM, navigate to `Contributions → + Create`. The
   form should now show a `Name` input field at the top of the
   Identification panel. Filling in the form (including a value
   for Name) and clicking Save should succeed without the
   `Field: name, Validation: required` error.

## 6. Commit

Single commit, message:

```
feat(layout): auto-place required `name` field on detail layouts

EspoCRM treats `name` as required on every entity. YAMLs in CBM
build detail layouts from category-driven `tabs:` blocks; the
system `name` field has no category, so the tab-expansion logic
in LayoutManager._expand_tabs never places it. The result was a
create form with no `name` input and a guaranteed save failure
on every record-creation attempt: 'Field: name, Validation:
required'. Every CBM custom-entity YAML had this latent failure.

This change makes LayoutManager auto-prepend a `name` row to
detail/edit layouts that do not explicitly place it. The rule:
- Scan the built panel payload for any cell named `name`.
- If found anywhere, do nothing — respect explicit placement.
- Otherwise prepend [{"name": "name"}] as the first row of the
  first panel without dynamicLogicVisible (i.e., the first
  always-visible panel). Falls back to the first panel if every
  panel is conditional.
- Skip when there are zero panels (YAML-shape problem).

Adds entity setting `settings.autoPlaceName` (default true). Set
false when `name` is supplied by a formula or workflow and a
manual input would be wrong.

Threading: process_layouts derives the flag from
entity_def.settings.autoPlaceName and passes it through
_process_one_layout → _build_payload → _build_detail_payload to
the new helper _ensure_name_placed. List-layout path is
unchanged — list columns already declare `name` explicitly.

Adds five tests covering: default prepends; explicit placement
not duplicated; opt-out flag honored; conditional first panel
skipped in favor of first always-visible; all-conditional fallback
to first panel.

Schema doc updated (Section 5.4) with the new setting and rationale.

After this change, the next Configure run against any CBM custom
entity will auto-heal its detail layout — the comparator detects
the new `name` row in the desired payload, the writer fires.
```
