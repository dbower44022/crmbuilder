# Layout fixtures — ground truth from a live EspoCRM 9.x instance

Captured read-only by `tools/capture_layouts.py` via
`GET /Layout/action/getOriginal?scope=<entity>&name=<type>` against the CBM test
instance, for one native entity (`Contact`) and one custom entity
(`CClientProfile`). These drive the builder/reverse-mapper tests so the YAML
engine round-trips every layout type losslessly.

`getOriginal` returns the effective (customized) layout, or `false` when the type
is not separately defined (e.g. `edit` derives from `detail`). Empty/`false`
responses are intentionally **not** saved as fixtures.

## Structure classes (the dispatch key throughout the engine)

| Class | Layout types | Saved structure |
|---|---|---|
| **A** panels/rows | `detail`, `edit`, `detailSmall`, `detailConvert` | `list[panel]`; panel keys `customLabel`/`label`, `style`, `tabBreak`, `tabLabel`, `hidden`, `noteText`, `noteStyle`, `dynamicLogicVisible`, `rows`. Cells are `{"name": <field>}` (+ optional `fullWidth`/`noLabel`/`view`/`customLabel`). |
| **B** columns | `list`, `listSmall`, `kanban` | `list[column]`; keys `name` (req) + optional `link`(bool), `width`(int), `notSortable`(bool), `align`, `view`. |
| **C** flat name list | `filters`, `massUpdate`, `relationships` | `list[str]` — field names (`filters`/`massUpdate`) or relationship link names (`relationships`). |
| **D** dict map | `sidePanels{Detail,Edit,DetailSmall,EditSmall}`, `bottomPanels{Detail,Edit,DetailSmall,EditSmall}` | `{name: cfg}` where `cfg` is `{disabled:true}` \| `{index:N}` \| `{index,tabBreak,tabLabel}` \| `{index,sticked}`. Meta keys `_delimiter_`, `_tabBreak_<n>`. |

Field-name normalization (c-prefix on native entities) applies to cell names
(A), column `name` (B), and field-name entries in `filters`/`massUpdate` (C).
Relationship link names (C `relationships`, D map keys) are deterministic from
the `relationships:` block and are stored verbatim.

Portal variants (`*Portal`) exist as a scope but had no defined layouts on the
captured instance; deploy support is deferred. Layout Sets (per-team/role) are
out of scope (supersedes DEC-6).
