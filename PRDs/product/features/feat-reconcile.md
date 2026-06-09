# Feature: CRM ↔ YAML Drift Reconciliation

**Status:** In progress (V1 app). Phase 1 write-back core built + proven; diff
engine in progress.
**Branch / worktree:** `v1-reconcile-yaml-drift` (isolated git worktree at
`~/Dropbox/Projects/crmbuilder-reconcile`, off `main`).
**Package:** `espo_impl/core/reconcile/`.

## 1. Goal

Compare the **live EspoCRM configuration** against the original **YAML program
files**, present every difference in a tree/checklist for selective approval, and
write the accepted differences back into the source YAML — preserving comments
and structure, bumping `content_version`, and emitting a provenance report.

The feature is **one-way (CRM → YAML)**; the live CRM is never written to. It
exists because configuration drifts: changes made through the EspoCRM admin UI
leave the deployed system out of sync with the YAML that originally built it.

## 2. Design contract (locked decisions)

1. **Versioning:** bump `content_version` inside the file; **git carries
   history**. No `vN` files on disk. One canonical file per entity, edited in
   place — so the working-tree file is always the source of truth and always
   what the next compare diffs against.
2. **Write-back = "Option B":** copy the original into a comment-aware model,
   apply **only the ticked deltas**, write back to the same path. Comments,
   ordering, `optionsDeferred` flags, and manual-config notes all preserved.
3. **Splice, don't re-dump.** The Phase 0 spike showed a whole-file `ruamel`
   dump normalizes inline flow-map spacing (`{ field: x }` → `{field: x}`) and
   drops hand-aligned columns. So the write-back layer uses `ruamel` purely as a
   **position-aware locator** (`.lc` line/column) and splices replacement text
   into the original source bytes — everything untouched stays byte-for-byte
   identical, and git diffs stay surgical.
4. **Output:** git commit (the machine-readable record) **+ a human-readable
   reconcile report** (reuse the `reporter.py` pattern → client repo `reports/`),
   recording each accepted drift as `old → new` with the provenance that it
   originated as a live-CRM/UI edit.
5. **Direction:** one-way CRM → YAML. **CRM is read-only.** A drift that turns
   out to be a mistake is fixed in YAML and re-deployed via the normal Configure
   flow.
6. **One-sided handling = a + b:**
   - (a) **changed-in-both** → surgical scalar `set`.
   - (b) **CRM-only additions** (added via UI, in no YAML) → reconstruct the
     field from live CRM + **insert**, with **ask-per-addition** for the target
     file (entities span multiple domain files: MR-/FU-/CR-Contact, etc.).
   - (c) **YAML-only** (in YAML, absent from CRM) → **reported, never
     auto-deleted** (ambiguous: deleted-in-UI vs. never-deployed).
7. **Scope = all readable config types**, built and verified **type-by-type**:
   fields → relationships → layouts → security/teams → filtered tabs → (saved
   views / duplicate checks / workflows, pending an empirical read-back check).
   Note: "no REST *write* path" for the last three is irrelevant here (we only
   read); they live in GET-able metadata, so they are likely readable.
8. **UX:** a tree/checklist panel grouped by entity → config type → item, each
   with a checkbox and `old → new`, matching the Configure/Audit panel idiom. A
   `CRM_ONLY` row exposes an inline target-file picker. "Reconcile Selected"
   applies, bumps, and reports.

## 3. Reuse vs. build

**Reuse:** `audit_manager.py` (live read), `comparator.py` `FieldComparator`
(field diff), `config_loader.py` (YAML → `ProgramFile` models + provenance),
`reporter.py` (report pattern), `main_window.py` (panel surface).

**Build:** comment-preserving splice write-back (`ruamel`), a unified diff engine
with one comparator per config type, the locator/resolver/patcher layer, a
field-reconstruction serializer (for additions), a provenance index (entity/field
→ owning file), a reconcile worker, and the tree/checklist panel.

## 4. Core data model

`Difference { config_type, category (CHANGED|CRM_ONLY|YAML_ONLY), entity,
locator, property, yaml_value, crm_value, source_file, full_crm_block }`. The
diff engine emits `list[Difference]`; the panel renders it; the worker consumes
the ticked subset; the patcher applies via the locator. The comparator never
knows about `ruamel`; the writer never re-runs comparisons.

## 5. Build sequence

- **Phase 0 — round-trip safety gate.** *(Done — spike confirmed `ruamel`
  preserves everything except inline flow-map spacing; hence splice.)*
- **Phase 1 — fields, end-to-end.** Write-back core *(done, commit `21fce1fa`)*;
  diff engine *(in progress)*; then live-state capture, CRM-only insertion +
  ask-per-addition, worker, panel.
- **Phase 2 — relationships** (clean list-by-name targeting).
- **Phase 3 — layouts** + **security** comparators — **deferred** until the
  parallel YAML schema-expansion work (adding layout types + security to the
  schema) lands; built once against the final models. Re-run Phase 0 after that
  merge.
- **Phase 4 — filtered tabs**, then the metadata-only types after an empirical
  read-back check against the live instance.

## 6. Node targeting (the crux)

Typed locators (`FieldLocator`, `RelationshipLocator`, `LayoutLocator`) decouple
"what differs" from "where it lives". List-item-by-name for fields/relationships
(scan the `CommentedSeq` for the matching `name`); positional panel/row/column
for layouts (the hard case). The patcher applies `set` (Phase 1), `insert`
(CRM-only additions, later), and `delete` (built with comment-orphan care but
unused in v1, since YAML-only is report-only).

## 7. Status

Phase 1 write-back core: `YamlDocument.set_scalar`, `patcher.set_field_property`,
typed locators — 7 passing tests, validated in-memory on a real `MN-Session.yaml`
(one line changed; folded blocks, comments, aligned flow clauses all intact).
Dependency `ruamel.yaml>=0.18` added.
