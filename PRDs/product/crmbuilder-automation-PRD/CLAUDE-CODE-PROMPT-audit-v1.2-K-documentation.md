# CLAUDE-CODE-PROMPT — audit-v1.2-K — Documentation Updates

**Repo:** `crmbuilder`
**Series:** `audit-v1.2` (eleven-prompt sequence implementing the v1.2
expansion of the Audit feature per
`PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` v1.3)
**Last Updated:** 05-25-26 00:45
**Spec:** No schema doc edits in this prompt — schema-spec patches
already shipped in Prompt G. This prompt updates user-facing and
implementation-reference docs.
**Planning:** `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md`
§5 Prompt K.
**Depends on:** All prior audit-v1.2 prompts (A through J). All
implementation work is complete; this prompt records what shipped
in operator-readable form.
**Governance:** No new decisions in this prompt. Documents the
seven DECs already queued for this conversation's close-out.

## Position in the Series

This is **Prompt K — the final prompt.** Pure documentation rendering;
no code changes, no new tests, no migration. After Prompt K lands,
the audit-v1.2 series is complete and the conversation moves to
close-out: the seven accumulated DECs formalized in a SES-NNN
close-out payload against the CRMBUILDER engagement, plus the
Claude Code apply prompt rendered inline.

## Scope Resolutions From Kickoff

Three framing decisions resolved at Prompt K kickoff (with default
"confirm" approval from Doug):

1. **No new `docs/user/user-guide.md` file.** The planning doc §5
   Prompt K mentioned updating it, but the file doesn't exist in the
   repo and no other `docs/user/` files exist either. Operator-facing
   content for v1.2 folds into the existing `feat-audit.md` §8 UI
   Integration section — which already leans operator-facing in v1.1.
2. **Screenshots as placeholders.** Claude Code captures the
   screenshots at execution time; this prompt specifies file paths
   and what each screenshot should show. Three screenshots needed
   (listed below in §1).
3. **`CLAUDE.md` updates kept high-level.** `CLAUDE.md` is a
   session-orientation doc, not a code registry. v1.2 additions
   merit a brief note in the relevant section, not enumeration of
   every new dataclass. Updates target the high-level audit-feature
   capability summary, not the detailed file inventory (which lives
   in `feat-audit.md` §9).

## Scope

In scope:

1. `PRDs/product/features/feat-audit.md` — version bumped from
   1.1 → 1.2; content updates per §1 below
2. `CLAUDE.md` — high-level v1.2 note added to the relevant section
   per §2 below
3. Three screenshot placeholders captured by Claude Code at
   execution time per §3 below

Out of scope:

- Code changes (none — series complete)
- Schema-spec edits (already shipped in Prompt G)
- New user-guide.md file (per kickoff resolution)
- CLAUDE.md detailed file inventory (per kickoff resolution)
- Audit-trail v1.4 deferred items (out of scope for this series)
- Engine-pluggability documentation (separate workstream)

## Working Method

No code; no tests; no ruff. Documentation rendering against the
existing v1.1 doc structure.

```bash
# Optional: verify markdown renders cleanly in a viewer
# Optional: confirm screenshot paths exist after capture
```

## Files to Modify

### 1. `PRDs/product/features/feat-audit.md` — v1.1 → v1.2

**Front matter update.** Lines 1–7 currently read:

```markdown
# CRM Builder — CRM Audit

**Version:** 1.1
**Status:** Implemented
**Last Updated:** April 2026
**Depends On:** app-yaml-schema.md, feat-fields.md, feat-layouts.md, feat-relationships.md, feat-entities.md
```

Update to:

```markdown
# CRM Builder — CRM Audit

**Version:** 1.2
**Status:** Implemented
**Last Updated:** 05-25-26 [HH:MM at commit time]
**Depends On:** app-yaml-schema.md, feat-fields.md, feat-layouts.md, feat-relationships.md, feat-entities.md
```

(Use the `MM-DD-YY HH:MM` convention per project standards.)

**Add a version-1.2 callout near the top.** Insert after the front
matter and before the §1 Purpose header — a short "What's New in
v1.2" callout block linking to the relevant new content:

```markdown
---

**What's New in v1.2**

- **Security audit** — Roles and Teams are discovered alongside
  entities, with `scope_access:` and `system_permissions:` per
  Section 12.1–12.4 of the YAML schema. Emitted to
  `<output_dir>/security/security.yaml`. See §2.2 and §5 for
  capture and output details
- **Filtered-tab audit** — EspoCRM's three-artifact filtered-tab
  pattern (Report Filter + scopes JSON + clientDefs JSON +
  i18n label patch) is reverse-engineered into structured
  `filteredTabs:` blocks in the per-entity YAML output. See
  §2.2 and §9.3
- **Entity picker** — Operators choose which entities to audit
  via a scrollable list with Select All / Select None buttons.
  Pre-flight discovery on dialog open. See §8.1
- **Section 12.5 role-aware visibility — NOT_AUDITABLE in v1.3.**
  EspoCRM 9.x Dynamic Logic has no role-condition type;
  Layout Sets bind to Teams, not Roles. The YAML schema can
  still express role-aware visibility intent (loader validates,
  audit round-trips the rest of §12). Deployment of §12.5 is
  deferred to v1.4 alongside §12.7 field-level permissions.
  See §6 and §10

---
```

**§2.2 Audit Scope.** The existing table:

```markdown
### 2.2 Audit Scope

An audit discovers the following from the source instance:

| Object | What Is Captured |
|--------|-----------------|
[...existing rows...]
```

Add three new rows after the existing list:

```markdown
| Role (Section 12.1) | Name, description, scope_access (per-entity access matrix), system_permissions (Section 12.4). Persona metadata is NOT captured (documentation-only in YAML per DEC-178; operators reattach manually after import) |
| Team (Section 12.2) | Name, description. Team-to-user membership is not captured (runtime data per Section 12.2) |
| Filtered tab | Per-entity navigation tabs backed by Report Filter records. Scope name, label, filter criteria, ACL strategy. Tabs without recognizable filter criteria are captured with label and scope but no filter block (operator hand-writes after import) |

#### What is NOT captured

The following are intentionally outside the audit's reach in v1.3:

| Object | Reason |
|--------|--------|
| Section 12.5 role-aware visibility | EspoCRM 9.x Dynamic Logic has no role-condition type; manually-configured role-aware visibility (via Dynamic Handler JS or Layout Sets + Teams) is operator-written code, not reverse-engineerable structured metadata. Audit log emits a NOT_AUDITABLE advisory per run. Deferred to v1.4 |
| Section 12.7 field-level permissions | Deferred to v1.4 |
| Workflows | Existing v1.1 limitation; no public REST API write path |
| Saved views, duplicate-check rules | Existing v1.1 limitations |
```

**§4 Audit Operations — extend with security and filtered-tab
operations.** Add a new sub-section after the existing operation
documentation:

```markdown
### 4.5 Security Audit (v1.2)

The security audit step runs after entity/field/layout discovery
and before YAML emission. It walks the source instance's roles
and teams and translates each into the schema's structured form:

- `client.get_roles()` fetches all Role records via REST
- `client.get_teams()` fetches all Team records via REST
- `AuditManager._reverse_scope_access()` translates each Role's
  `data` field — keyed by EspoCRM wire-name (e.g., `CEngagement`)
  — to YAML scope_access keyed by natural name (e.g., `Engagement`)
- `AuditManager._reverse_system_permissions()` reads the five
  schema-managed permission columns (`assignmentPermission`,
  `userPermission`, `exportPermission`, `massUpdatePermission`,
  `portalPermission`) and translates to the schema's
  `system_permissions:` block

Three EspoCRM-only permissions on the v1.2 preservation list
(`followerManagementPermission`, `groupEmailAccountPermission`,
`dataPrivacyPermission`) are NOT captured — the schema has no
representation for them.

Output: `<output_dir>/security/security.yaml` containing
`teams:` and `roles:` blocks. The file is only emitted when
something was captured (no empty placeholder file).

Per DEC-179, roles with empty `scope_access:` emit an
informational warning in the audit log; the role is still
emitted in YAML.

### 4.6 Filtered-Tab Audit (v1.2)

The filtered-tab audit reverse-engineers EspoCRM's three-artifact
filtered-tab pattern. For each audited entity:

1. `client.get_all_scopes()` (called once at start) enumerates
   custom tab-scopes (filter: `isCustom: true` AND `tab: true`
   AND `entity: false`)
2. `client.get_client_defs(scope_name)` per tab-scope recovers
   the entity binding and Report Filter ID
3. `client.list_report_filters(entity_wire_name)` per entity
   fetches the Report Filter records; HTTP 404 means Advanced
   Pack is not installed and the audit logs an informational
   note and continues
4. `AuditManager._reverse_where_items()` inverts the deploy
   side's `_to_where_items()` translation: EspoCRM where-items
   (with `{type, attribute, value}` shape) become parsed
   condition AST nodes; compound `and`/`or` groups become
   AllNode/AnyNode; `currentUser`/`notCurrentUser` map to the
   `$user` sentinel

Output: per-entity YAML files include a `filteredTabs:` block
when the entity has any filtered tabs.

Two limitations documented for v1.3:

- Unknown where-item types poison the entire filter — tab is
  captured with label and scope but no `filter:` block;
  operator hand-writes after import. Better than silently
  dropping conditions and changing the operator's intent
- Relative-date tokens (Section 11) are not reverse-engineered;
  post-deploy values are absolute `YYYY-MM-DD` strings;
  operators manually convert back to relative form if desired
```

**§5 Output and Reporting — document `security/security.yaml`.**
The existing §5 describes per-entity YAML output. Add a
sub-section after the existing content:

```markdown
### 5.4 Security YAML Output (v1.2)

When the security audit captures any roles or teams, the audit
writes `<output_dir>/security/security.yaml`. Structure:

```yaml
teams:
  - name: Mentor Administrators
    description: Members can manage mentor onboarding
  - name: System Administrators
    description: null

roles:
  - name: Mentor
    description: Active mentors
    persona: null  # Always null on capture; operator reattaches
    scope_access:
      Engagement:
        create: true
        read: own
        edit: own
        delete: no
        stream: own
    system_permissions:
      assignment_permission: team
      user_permission: team
      export: false
      mass_update: false
      portal: false
```
```

(The fence styling needs to be `~~~yaml` or escaped backticks if
Markdown renderer requires.)

**§6 Validation Rules — add v1.2 validations.** Add a new
sub-section:

```markdown
### 6.4 Role-Aware Visibility (v1.2)

Section 12.5 role-aware visibility validates at parse time but is
NOT_SUPPORTED for deploy on EspoCRM 9.x:

- Field-level `visibleWhen:` containing `role:` clauses: loader
  validates against `ProgramContext.role_names`; deploy emits
  NOT_SUPPORTED for the dynamic-logic visible block (field still
  deploys without visibility control)
- Layout-level `forRoles:` variant form: loader validates the
  coverage rule (every role in `program.roles` appears in exactly
  one variant's `forRoles:`); deploy emits NOT_SUPPORTED for the
  whole layout

The MANUAL CONFIGURATION REQUIRED advisory block at the end of
each deploy run lists affected fields and layouts so the operator
can configure them manually post-deploy.

See `PRDs/product/app-yaml-schema.md` §12.5 "Deploy Support" for
the workaround paths available to operators (Dynamic Handler JS;
Layout Sets + Teams).
```

**§8 UI Integration — update §8.1 and add §8.4.** Replace the
existing §8.1 sidebar entry list:

```markdown
### 8.1 Sidebar Entry

The Audit feature adds a new entry to the Deployment window
sidebar between Run History and Output:

```
Instances | Deploy | Configure | Run History | Audit | Output
```

The Audit entry contains:

1. **Source instance picker** — Dropdown filtered to instances
   with role `source` or `both`. Shows instance name and URL.
2. **Entity picker (v1.2)** — Scrollable list of all entities
   discovered on the active instance via a pre-flight
   `get_all_scopes()` call when the entry is first shown for
   that instance. Each entity has a checkbox (default checked).
   Two buttons above the list: **Select All** and **Select
   None**. When the operator switches to a different instance,
   the picker re-discovers from the new source. If pre-flight
   fails (HTTP error), the picker stays empty and the loading
   label switches to an error message; the audit can still run
   with default all-entities behavior.
3. **Scope options** — Checkboxes (all checked by default):
   - Include custom entity fields
   - Include native entity custom fields
   - Include detail layouts
   - Include list layouts
   - Include relationships
   - **Security (roles and teams)** *(v1.2; default checked
     per DEC-180)*
   - **Filtered tabs** *(v1.2; default checked per DEC-180)*
4. **Include native fields checkbox** — Unchecked by default.
   When checked, native fields on native entities are included
   in output.
5. **Start Audit button** — Initiates the audit. Follows the
   never-disable pattern: if no source instance is selected,
   clicking shows an explanatory message. If no entities are
   selected, clicking shows a "no work to do" message and does
   not launch the progress dialog.
6. **Last audit info** — Shows timestamp and output folder of
   the most recent audit for the selected source instance.

[Screenshot: `PRDs/product/features/feat-audit-v1.2-audit-entry.png`
 — full Audit entry view with picker populated and all checkboxes
 visible. Capture at Claude Code execution time.]
```

Add a new §8.4 after the existing §8.3:

```markdown
### 8.4 Overwrite Confirmation (v1.2)

When the operator clicks **Start Audit** and the output directory
already contains audit YAML output (any `*.yaml` at the program
root OR any `security/*.yaml` under the subdirectory), a
confirmation dialog fires per DEC-181:

> Output directory contains N existing audit YAML file(s); running
> this audit will overwrite them. Proceed?

Default focus is Cancel; the operator must explicitly choose
Proceed to continue. Cancel returns to the audit-entry view
without starting the audit.

Under the current `audit-{timestamp}` naming convention, this
dialog rarely fires in practice — only on second-runs within the
same second (timestamp collision). The check is in place for any
future move to a fixed-name output directory.

[Screenshot: `PRDs/product/features/feat-audit-v1.2-overwrite-dialog.png`
 — overwrite-confirmation QMessageBox with Cancel button focused.
 Capture at Claude Code execution time.]
```

**§9 Implementation Reference — extend §9.1 File Inventory.** Add
new rows to the existing table for the v1.2 file inventory:

```markdown
| Core | `espo_impl/core/team_manager.py` *(v1.2)* | `TeamManager` CHECK→ACT for team deploy |
| Core | `espo_impl/core/role_manager.py` *(v1.2)* | `RoleManager` CHECK→ACT for role deploy, including `_preflight_scope_access` per DEC-178 |
| API | `espo_impl/core/api_client.py` *(v1.2 additions)* | `get_teams()`, `get_roles()` for audit-side discovery; team / role CRUD endpoints for deploy |
| DB | `automation/db/migrations.py` *(v1.2 additions)* | `_client_v15` adds `Role` / `Team` tables; `_client_v16` adds `FilteredTab` table |
| Audit | `espo_impl/core/audit_manager.py` *(v1.2 extension)* | `_discover_teams`, `_discover_roles`, `_discover_filtered_tabs`; `_reverse_scope_access`, `_reverse_system_permissions`, `_reverse_where_items`/`_reverse_where_item`; new dataclasses `RoleAuditResult`, `TeamAuditResult`, `FilteredTabAuditResult`, `LayoutVariant` |
| Pipeline | `espo_impl/workers/run_worker.py` *(v1.2 extension)* | New Step 11 "Security" inserted between Workflows (Step 10) and Filtered tabs (renumbered Step 12); `_emit_manual_config_block` surfaces §12.5 NOT_SUPPORTED items |
| UI | `automation/ui/deployment/audit_entry.py` *(v1.2 extension)* | Entity-picker `QListWidget`, Security / Filtered tabs checkboxes, overwrite-confirmation dialog |
| UI | `automation/ui/deployment/configure_progress.py` *(v1.2 extension)* | Multi-file queue stable-sort placing security YAMLs last per Section 12.6 |
| Schema | `PRDs/product/app-yaml-schema.md` *(v1.2 patches)* | §12.5 NOT_SUPPORTED on EspoCRM 9.x (deferred to v1.4); §12.6 deploy ordering corrected to security-last |
```

**§9.2 Architecture Decisions — add v1.2 decisions.** Add new
paragraphs after the existing v1.1 architecture-decision content:

```markdown
**§12.5 deploy is NOT_SUPPORTED on EspoCRM 9.x (DEC-6).** EspoCRM
9.x Dynamic Logic has no role-condition type; Layout Sets bind to
Teams not Roles. Section 12.5 role-aware visibility ships at the
YAML/loader/validator/audit-passthrough surface but not at deploy.
Operators using EspoCRM 9.x configure role-aware visibility
manually via Dynamic Handler JavaScript or Layout Sets + Teams.
Deferred to v1.4 alongside §12.7 field-level permissions.

**Deploy ordering is security-LAST (DEC-5).** Files declaring
`roles:` or `teams:` deploy after files declaring entities so the
scope_access pre-flight in `role_manager._preflight_scope_access`
can validate against server state. Earlier drafts of the schema
spec prescribed security-first; investigation confirmed no
write-time validation in EspoCRM (references resolve at view-time),
so the pre-flight design dictates the order. Schema §12.6
corrected at v1.2.

**Pre-flight server-state validation (DEC-178).** `role_manager`
fetches the current scope list at the start of role deploy and
validates that every `scope_access:` entity reference resolves on
the target. Roles with unresolvable references receive a clear
pre-deploy error rather than the silent-accept-or-confusing-HTTP-
error behavior EspoCRM provides at write time.

**audit_log removed from §12.4 (DEC-176).** The schema's earlier
`audit_log:` permission was based on an EspoCRM 8.0 column that
9.x no longer manages via Role records. Removed entirely from the
v1.3 schema rather than carrying a vestigial field.

**Three EspoCRM-only permissions preserved on PATCH (DEC-177).**
`followerManagementPermission`, `groupEmailAccountPermission`, and
`dataPrivacyPermission` are not in the v1.3 schema but exist on
the EspoCRM Role record. `role_manager` PATCH operations preserve
them rather than nulling them out — operators who configure these
manually on the target retain their settings across deploys.
```

**§10 Future Considerations — update.** Move "Audit-trail
ConfigurationRun history" from Future to Done. Add new Future
entries:

```markdown
- **Section 12.5 deploy support (v1.4).** Role-aware field/panel
  visibility and layout-level forRoles variants need a real
  deploy mechanism. Candidates: Dynamic Handler JS generation,
  Teams-as-proxies-for-Roles, or EspoCRM upstream feature
  request for role-condition Dynamic Logic
- **Section 12.7 field-level permissions (v1.4).** Field-level
  read / write / require / hide permissions per role, paired
  with the §12.5 deferred work
- **Diff-aware overwrite confirmation.** The
  `(instance_id, entity_yaml_name, tab_id)` unique-key triple in
  the FilteredTab client-DB table supports per-file diff
  rendering before overwrite. Current implementation per DEC-181
  is a simple existence check. Candidate enhancement if
  operator feedback warrants
- **Refresh-entity-list button.** The current picker re-discovers
  scope only when the operator switches instances. A manual
  refresh button would handle mid-session server-side changes
  without requiring an instance switch
```

### 2. `CLAUDE.md` — high-level v1.2 note

Locate the audit-related section (the line at 127 mentions
`audit_worker.py`). Extend the surrounding context with a brief
mention of the v1.2 capabilities:

```markdown
Audit (v1.2): discovers entities/fields/layouts/relationships,
security (roles, teams), and filtered tabs from a source
instance. Emits structured YAML to the timestamped
`programs/audit-YYYYMMDD-HHMMSS/` directory plus
`security/security.yaml` for the security half. Operator
selects entities via picker; security and filtered-tab capture
gated by checkboxes (default on per DEC-180). Section 12.5
role-aware visibility is NOT_AUDITABLE in v1.3 — operators
configure it manually on the target.
```

No file-inventory enumeration. The detail belongs in
`feat-audit.md` §9.

### 3. Screenshot Placeholders

Three screenshots referenced from `feat-audit.md` v1.2 — to be
captured at Claude Code execution time. File paths and content
descriptions:

1. **`PRDs/product/features/feat-audit-v1.2-audit-entry.png`**
   The full Audit entry view: source instance picker at top,
   entity picker populated with several entity names (some
   custom, some native), Select All / Select None buttons visible,
   all six scope checkboxes (custom fields, native fields, detail
   layouts, list layouts, relationships, Security, Filtered tabs)
   visible with default check states. Resolution: matching the
   existing v1.1 screenshots if any are present; otherwise
   1200×800 or similar. PNG format.
2. **`PRDs/product/features/feat-audit-v1.2-overwrite-dialog.png`**
   The QMessageBox warning dialog with text "Output directory
   contains N existing audit YAML file(s); running this audit
   will overwrite them. Proceed?" and Cancel button focused
   (highlighted). Captured against an output directory containing
   one or two stub YAML files for realism.
3. **`PRDs/product/features/feat-audit-v1.2-manual-config-block.png`**
   Terminal/log screenshot of a deploy run that produced
   NOT_SUPPORTED items for §12.5 role-aware visibility — the
   MANUAL CONFIGURATION REQUIRED block at the end of the run
   listing affected fields and layouts. Captures the
   operator's visibility into what they need to configure
   manually.

When Claude Code executes this prompt, it should capture the
three screenshots and place them at the file paths above. If
screenshot capture is impractical in the execution environment,
record placeholder paths in the doc with TODO comments and ask
Doug to capture them manually after.

## Acceptance Criteria

1. `PRDs/product/features/feat-audit.md` version updated 1.1 → 1.2;
   Last Updated stamp current per MM-DD-YY HH:MM format
2. "What's New in v1.2" callout block added near the top with
   four bullet items covering security audit, filtered-tab audit,
   entity picker, and §12.5 NOT_AUDITABLE
3. §2.2 Audit Scope extended with three new captured-object rows
   (Role, Team, Filtered tab) and a "What is NOT captured"
   sub-section
4. §4 Audit Operations extended with §4.5 Security Audit and §4.6
   Filtered-Tab Audit sub-sections
5. §5 Output and Reporting extended with §5.4 Security YAML Output
   sub-section showing the canonical security.yaml shape
6. §6 Validation Rules extended with §6.4 Role-Aware Visibility
   sub-section documenting the NOT_SUPPORTED treatment
7. §8 UI Integration §8.1 updated with entity picker, security and
   filtered-tab checkboxes; new §8.4 Overwrite Confirmation
   sub-section
8. §9 Implementation Reference §9.1 File Inventory extended with
   v1.2 file rows; §9.2 Architecture Decisions extended with v1.2
   decisions (DECs 5, 6, 7, 176, 177, 178, 179)
9. §10 Future Considerations updated: audit-trail completed item
   moved to Done; new entries for §12.5 / §12.7 v1.4 deferrals,
   diff-aware confirmation, and refresh-picker enhancements
10. `CLAUDE.md` updated with high-level v1.2 audit note
11. Three screenshot placeholders captured (or marked TODO) at the
    paths in §3
12. Commit and push with a clear message documenting the version
    bump and content additions

## Out of Scope

- Code changes (the implementation series is complete after
  Prompts A through J)
- Schema-spec edits (already in Prompt G)
- New user-guide.md (per kickoff resolution; operator-facing
  content folds into feat-audit.md §8)
- CLAUDE.md detailed file inventory (per kickoff resolution)
- v1.4 deferred items documented as Future Considerations only,
  not implemented

## Reporting Back

When finished, report:

- Modified file paths and line counts
- Screenshots captured (paths and whether captured live or marked
  TODO)
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Confirmation that the audit-v1.2 series is complete

After Prompt K lands, the conversation moves to **close-out**:

1. Verify next-available SES identifier against the CRMBUILDER
   engagement's db-export snapshot at
   `crmbuilder/CRMBUILDER/db-export/sessions.json` (or similar
   per repo-level CLAUDE.md)
2. Author seven DECs (or six if DEC-6 and DEC-7 merge per the
   kickoff suggestion) in a close-out payload at
   `crmbuilder/CRMBUILDER/close-out-payloads/ses_NNN.json`
3. Author the Claude Code apply prompt at
   `crmbuilder/CRMBUILDER/apply-prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`
4. Render the apply prompt inline so Doug can scan its planned
   net effect
5. Commit and push both files in the same turn (sandbox
   convention)
6. Doug runs the apply prompt locally via Claude Code, which
   executes the apply script against the CRMBUILDER engagement's
   database and POSTs every record to the V2 API in the standard
   fixed order
