# PI-020 — Cross-file layout aggregation (REQ-403)

**Release:** REL-017 · **Project:** PRJ-047 · **Date:** 2026-07-01

## The problem

EspoCRM stores one detail layout per entity and the save-layout call **replaces**
the whole layout. The deploy engine runs one program file at a time and writes
each file's layout independently, so when two files declare `layout:` blocks for
the same entity (e.g. `MN-Account` and a future `CR-Account` both adding a panel
to `Account`), **only the last file's panels survive** — the earlier file's are
clobbered. This blocked the methodology pattern where several domains each
contribute their own panels to a shared native entity.

## Design (panel ordering: Option A, chosen)

A **pre-loop aggregation** merges every batched file's layout contributions for an
entity into a single layout, written once, before the per-file deploy loop:

- **`espo_impl/core/layout_aggregator.aggregate_layouts`** (pure, unit-tested):
  groups entity_defs across the batch by EspoCRM entity name; for each
  `(entity, layout_type)` with more than one contributor it merges the panel
  lists, ordered **by contributing file (alphabetical) then declaration order
  within a file** (Option A — simple and deterministic). The merged layout is
  assigned to the *canonical* (first-alphabetical) contributor and **stripped from
  the others**, so exactly one save-layout call writes the complete layout.
- **Conflict detection:** two files declaring a panel with the **same label** on
  the same entity is a conflict — reported (not silently merged) and the deploy is
  aborted before any ambiguous layout is written.
- **Cross-file field resolution:** a merged panel may reference a custom field
  declared in a *sibling* file. The canonical entity_def carries a new
  `layout_field_names` (the union of custom field names across contributors);
  `LayoutManager.process_layouts` uses it for c-prefix resolution on native
  entities, so a cell for `sponsorType` declared in another file still deploys as
  `cSponsorType`. `EntityDefinition.fields` is left untouched (field *deployment*
  stays per-file — the canonical file never deploys a sibling's fields).
- **Wiring:** `automation/ui/deployment/configure_progress.py` runs the aggregator
  after Pass-2 validation and before the deploy loop; a conflict aborts with a
  clear error, otherwise each program's entities are replaced with the merged set.

## Scope boundary (explicit)

- Aggregation is a **batch** operation. Re-deploying a **single** file on its own
  cannot merge with panels another file deployed in a prior batch (save-layout
  still replaces) — the same inherent constraint the requirement's acceptance
  assumes ("when multiple files declare layout blocks … [in the batch]"). Deploy
  the domain's files together.
- Panel-order **Option B** (an explicit per-panel `panelOrder` integer) was not
  built; Option A covers the methodology need. B can be added later without
  disturbing this design.

## Tests

- `tests/core/test_layout_aggregator.py` — merge, alphabetical-then-declaration
  ordering, the field-union hint, duplicate-label conflict (originals left
  untouched), single-contributor / different-entity / DELETE-action / non-panel
  layouts left alone.
- `tests/test_layout_manager.py::test_layout_field_names_hint_cprefixes_cross_file_field`
  — the hint drives c-prefix for a cross-file field end-to-end.
- Full layout + config regression: 344 passed.
