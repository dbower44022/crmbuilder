# REL-039 / PI-355 — Knowledge Inventory & Classification

**Requirement:** REQ-414 — *Inventory and classify all instruction-file and memory knowledge by destination.*
**Acceptance:** a classification artifact lists every instruction-file section and every memory file with its assigned destination and a one-line rationale, nothing unclassified.
**Produced:** 2026-07-01 (Claude Code, ENG-001). This is the authoritative work-list for the REL-039 migration (PI-356 design → PI-357 migrate → PI-358 bootstrap → PI-359 reduce → PI-360 rule).

## The six destinations (REQ-414)

| Tag | Meaning |
|---|---|
| **DELETE-DUP** | A duplicate of database-owned content — delete from the file (the DB already owns it). |
| **MIGRATE-DB** | Database-owned content (or an operational *lesson*) to migrate into the DB. |
| **MIGRATE-PREF** | A user preference (interaction/working style) to migrate. |
| **MIGRATE-PTR** | An external reference pointer (server, dashboard, doc, ticket) to migrate. |
| **STAYS-REPO** | Code or architecture reference that stays in the repository (`CLAUDE.md`). |
| **STAYS-BOOT** | Session bootstrap that must stay in the auto-loaded file. |

**Note on hybrids (a PI-356 design input):** many `project_*` memories and many `CLAUDE.md` v2 notes are *hybrid* — a historical build-status record (duplicates DB decisions/PIs/commits → DELETE-DUP) welded to a durable *gotcha/lesson* (not queryable in the DB → MIGRATE-DB). Where a file is hybrid, the table gives its **dominant** destination and the rationale flags the split; PI-357 splits them at migration time.

**Note on scope boundaries (a PI-356 design input):**
- The **file-based memory** lives at `/home/doug/.claude/projects/-home-doug-Dropbox-Projects-crmbuilder/memory/` — a Claude Code *harness* feature outside the repo, injected at session start. It is not reachable by the V2 REST API at runtime.
- The **global** `~/.claude/CLAUDE.md` is cross-project; it has no natural home in the crmbuilder-scoped V2 DB (ENG-001).
- Several `reference_cbm_*` and `project_cbm_*` memories are **CBM-client** knowledge that arguably belongs to the CBM engagement/repo, not ENG-001. Flagged inline.

---

## Part 1 — Global instruction file: `~/.claude/CLAUDE.md` (26 lines, 1 section)

| Section | Destination | Rationale |
|---|---|---|
| "Respect each repository's own process — including across repos" | **STAYS-BOOT** | Cross-project operating rule; global scope has no home in the crmbuilder-scoped V2 DB. Candidate for a future global-preference store, not this migration. |

---

## Part 2 — Project instruction file: `CLAUDE.md` (877 lines, 14 top-level sections)

| Section / note group | Destination | Rationale |
|---|---|---|
| **Current direction: Master CRMBuilder PRD consolidation** | **MIGRATE-DB** | Current project direction/goal — governance/project state the DB should own; leave a one-line bootstrap pointer. |
| Current focus / Approach / Documents being consolidated / Format rule (05-26-26) | **MIGRATE-DB** | Project state + a preference (MD-only format rule → could be MIGRATE-PREF); DB-owned project context. |
| **Project** (CRM Builder description, EspoCRM lifecycle) | **STAYS-REPO** | Architecture/product reference describing the codebase. |
| Note on the CBM repo's local directory name | **MIGRATE-PTR** | A reference pointer (repo name ↔ local path mapping); belongs with CBM engagement pointers. |
| **CRMBuilder v2 — Methodology Rearchitecture** (intro) | **STAYS-REPO** | Orientation to what v2 is; architecture reference. Leave a short pointer; detail is DB-owned. |
| v2 §: Storage system v0.1 landed; Session orientation protocol (DEC-011); Conduct framework (charter/kickoff/question-library) | **MIGRATE-DB** | Governance/process rules and decisions the DB owns (DEC-011, conduct docs are methodology). Duplicates DB decisions. |
| v2 §: Reference relationship vocabulary lives in `vocab.py`; v2 version source in `__init__.py` | **STAYS-REPO** | Points at code locations; architecture reference that must track the repo. |
| v2 §: Identifier-optional-on-POST (PI-002); `{data,meta,errors}` envelope; v0.7 governance entities; PI-β de-file/snapshots; PI-110 logging; Session/Conversation redesign (PI-073); governance model redesign (PI-112); ADO substrate (PI-114); ADO evolution; Agent Profile Registry (PI-122); registry/runtime notes (PI-330/339/340/341/343/346); Reconcile redesigns (REL-024/027/037); Postgres foundation (PI-α/β/γ) | **DELETE-DUP** | Historical build-status notes that duplicate DB decisions/PIs/commits. Dominant = delete after confirming each fact is a DB record; any embedded still-current *rule* (e.g. envelope-unwrap discipline, add-entity-type-needs-both-CHECKs) splits to MIGRATE-DB as a lesson. |
| v2 §: Requirements-provenance & review rebuild (ENG-001 founding); coverage baseline `2026-06-10`; **`crmbuilder.env` durable defaults** | **STAYS-REPO** | The `.env` baseline note is per-deployment/gitignored config reference that must live with the repo; the provenance-rebuild narrative duplicates DB (→ its facts DELETE-DUP). |
| **Working conventions** → Governance is a precondition (self-check); enforcement gate (REQ-320); retain-not-delete (REQ-264); push convention; **Branch-work protocol (Model A)**; session lifecycle (open/close/resolve); governance recording rules (TOP-013) | **MIGRATE-DB** | These are binding governance rules — TOP-013 already owns most; the rest should become governance_rule records. A minimal "read TOP-013 at session start" bootstrap pointer stays (STAYS-BOOT). |
| **Commands** (uv sync / run / pytest / ruff / docgen) | **STAYS-REPO** | Repo build/run reference; must track the code. |
| **Architecture** (code tree `espo_impl/`, `automation/`, `tools/`, `PRDs/`) | **STAYS-REPO** | Codebase architecture reference. |
| **Key Patterns** (c-prefix, entity-name mapping, project_folder, …) | **STAYS-REPO** | Code behaviour reference. |
| **Server Management Layer** (deploy/upgrade/recovery/version detection) | **STAYS-REPO** | Feature/architecture reference for the deployment code. |
| **Audit Feature** (v1.2/1.3 behaviour, DEC-180/181/182) | **STAYS-REPO** | Feature reference; the DECs also live in the DB (their records → DELETE-DUP) but the feature narrative stays. |
| **YAML Schema v1.1** + **YAML Schema Rules** (authoritative constraints, deployment validation pass table) | **STAYS-REPO** | Code-enforced schema rules + fix-history that must track the engine code. |
| **Document Production Process** (13-phase summary, pilot, PRD content rules) | **MIGRATE-DB** | Methodology — per the "specs live in DB" principle ([[project_v2_specs_live_in_db]]) methodology belongs in DB topics/requirements. Note: being consolidated into the Master PRD (REL-013). |
| **Known Limitations** (Path B batch back-fill gap) | **STAYS-REPO** | Code-state/architecture limitation reference. |
| **What NOT to Do** (don't add client YAML, don't call put_metadata, don't skip validate_program, …) | **STAYS-REPO** | Mostly code rules that track the codebase; a few (don't-ask-to-proceed style) overlap MIGRATE-PREF. |

---

## Part 3 — File-based memory (91 files)

### 3a. `feedback_*` — user guidance/preferences (16)

Binding *process/governance* feedback → **MIGRATE-DB** (as `governance_rule`); *interaction-style* feedback → **MIGRATE-PREF**. The DB structure for each is a PI-356 decision.

| File | Destination | Rationale |
|---|---|---|
| feedback_governed_by_trailer | MIGRATE-DB | Binding commit-governance rule (Governed-By trailer); a governance_rule. |
| feedback_terminology_governance | MIGRATE-DB | Binding rule (every term in glossary; no new term without approval). |
| feedback_full_governance_always | MIGRATE-DB | Binding requirement-first rule (REQ-248/DEC-538) — already DB-adjacent. |
| feedback_v2_governance_realtime | MIGRATE-DB | Binding rule: record governance real-time via API in Claude Code. |
| feedback_project_complete_is_terminal | MIGRATE-DB | Binding governance rule about project terminality. |
| feedback_agent_naming_convention | MIGRATE-DB | Binding naming rule (display name ends "Agent"). |
| feedback_commit_with_pathspec | MIGRATE-DB | Binding commit-hygiene rule. |
| feedback_commit_during_multi_session_work | MIGRATE-DB | Binding rule: commit immediately under parallel orchestrators. |
| feedback_approval_request_structure | MIGRATE-DB | Binding rule on how to structure approval requests. |
| feedback_no_confirmation | MIGRATE-PREF | Interaction style: execute autonomously, don't ask to proceed. |
| feedback_no_grayed_buttons | MIGRATE-PREF | UI preference (also encoded in code — partial DELETE-DUP vs What-NOT-to-Do). |
| feedback_button_styling | MIGRATE-PREF | UI preference (secondary buttons warm orange). |
| feedback_operator_control_over_multi_step_ops | MIGRATE-PREF | Interaction preference: don't auto-loop multi-step external ops. |
| feedback_one_issue_at_a_time_discuss | MIGRATE-PREF | Interaction preference for planning/design. |
| feedback_one_step_at_a_time | MIGRATE-PREF | Interaction preference for terminal walkthroughs. |
| feedback_full_file_paths | MIGRATE-PREF | Interaction preference: always full absolute paths. |

### 3b. `reference_*` — pointers & rules (6)

| File | Destination | Rationale |
|---|---|---|
| reference_cbm_production_server | MIGRATE-PTR | External server pointer (CBM prod). **CBM-scoped — candidate for CBM engagement, not ENG-001.** |
| reference_cbm_test_instance_connection | MIGRATE-PTR | External instance pointer (CBM test). CBM-scoped. |
| reference_cbm_docs_bookstack | MIGRATE-PTR | External docs pointer (CBM BookStack). CBM-scoped. |
| reference_cbm_bookstack_api | MIGRATE-PTR | External API pointer + token location. CBM-scoped. |
| reference_requirement_readability_gate | MIGRATE-DB | Not an external pointer — a DB/process rule (approval readability gate); belongs as a rule record. |
| reference_v2_closeout_schema_gotchas | MIGRATE-DB | Operational lesson (close-out wire-format gotchas); a `lesson`. |

### 3c. `project_*` — build records & lessons (69)

**Lesson-bearing** (durable gotcha/how-to not queryable in the DB) → **MIGRATE-DB** (`lesson`). **Current live-state** (infra/DB reality) → **MIGRATE-DB** (state). **Pure historical build-status** fully represented by DB decisions/PIs/commits → **DELETE-DUP**.

| File | Destination | Rationale |
|---|---|---|
| project_overview | STAYS-REPO | Restates the codebase identity — architecture reference (dup of CLAUDE.md Project §). |
| project_cloud_deployment_v2 | MIGRATE-DB | Current live cloud infra state + pointers (droplet, Managed PG, api.crmbuilder.ai). Authoritative operational state. |
| project_v2_live_db_is_postgres | MIGRATE-DB | Current live-DB state (PG, dual-head alembic). |
| project_v2_engagement_db_path | MIGRATE-DB | Current runtime model (X-Engagement header) — partly superseded; state. |
| project_v2_specs_live_in_db | MIGRATE-DB | Governing principle (specs live in DB as topic/req/decision) — a rule. |
| project_v2_changelog_check_migration_gotcha | MIGRATE-DB | Durable engineering lesson (add entity type → rebuild change_log CHECK). |
| project_v2_live_db_migrate_via_alembic_only | MIGRATE-DB | Durable operational rule (never hand-patch live schema). |
| project_v2_sqlite_wal_concurrency | MIGRATE-DB | Durable lesson (WAL fix) + PI status (PI-253 hybrid). |
| project_v2_catalog_data_gitignored | MIGRATE-DB | Durable lesson (catalog YAML absent → validate via create_all). |
| project_v2_closeout_broken_on_main | MIGRATE-DB | Durable lesson (close-out payload shape). |
| project_v2_scheduled_session_closeout | MIGRATE-DB | Durable lesson (planned-session close-out PATCH). |
| project_v2_mcp_remote_access | MIGRATE-DB | Current infra state + lesson (MCP at mcp.crmbuilder.ai; claude.ai-web blocked). |
| project_pg_autoassign_concurrency | DELETE-DUP | PI-384 build-status (Resolved, merged) — DB owns it; residual lesson splits to MIGRATE-DB. |
| project_pg_sequences_not_reset | MIGRATE-DB | Durable lesson (PG sequences left behind max(id); repair via setval). |
| project_pg_sideband_engagement_id_bug | MIGRATE-DB | Open-bug lesson (side-band writers stamp code not identifier). |
| project_qt_segfault_flake_fixed | MIGRATE-DB | Durable lesson (don't remove the gc/DeferredDelete teardown). |
| project_qt_worker_widget_gc_hazard | MIGRATE-DB | Durable lesson (deleteLater() on transient modal sub-dialogs). |
| project_export_dir_validation_relaxed | MIGRATE-DB | Durable behaviour lesson. |
| project_requirements_provenance | DELETE-DUP | Complete rebuild status (PR#4/#5) — DB owns the decisions/PIs; baseline note → STAYS-REPO (.env). |
| project_outstanding_work_release_plan | MIGRATE-DB | Governing model (release-scoped dev; REQ-211) — a rule/state. |
| project_manual_release_mode | DELETE-DUP | PI-294/295 build-status (SHIPPED) — DB owns it; gotcha splits to MIGRATE-DB. |
| project_pi288_release_gate | DELETE-DUP | PI-288 status — DB owns; the flag-behaviour rule splits to MIGRATE-DB. |
| project_open_release_triage_20260628 | DELETE-DUP | Point-in-time triage snapshot — superseded by live release records. |
| project_rel013_pi095_ingest_halted | DELETE-DUP | PI-095 status (DEC-884/SES-333/CNV-289) — DB owns; the "check target before bulk write" lesson splits to MIGRATE-DB. |
| project_rel040_participant_entity | DELETE-DUP | PI-094 status — DB owns; the /references pair-direction lesson splits to MIGRATE-DB. |
| project_pi020_layout_aggregation | DELETE-DUP | PI-020 status — DB owns. |
| project_pi046_reference_entity_type | DELETE-DUP | PI-046 status — DB owns. |
| project_pi103_edit_locking | DELETE-DUP | PI-103 status — DB owns. |
| project_pi123_stage2_3_done | DELETE-DUP | PRJ-019/PI-122 status — DB owns. |
| project_pi133_pi134_built | DELETE-DUP | PI-133/134 status — DB owns. |
| project_pi183_execution_mode | DELETE-DUP | PI-183/190 status — DB owns. |
| project_pi255_source_mapping | DELETE-DUP | PI-255 status — DB owns; RECONCILER-not-started note → MIGRATE-DB (state). |
| project_pi308_migration_drift_safety | DELETE-DUP | PI-308 status — DB owns; the safe-live-migrate how-to splits to MIGRATE-DB. |
| project_pi321_agent_secret_storage | DELETE-DUP | PI-321 status — DB owns; the un-run migrate command → MIGRATE-DB (open action). |
| project_pi330_agent_registry_ui | DELETE-DUP | PI-330 status — DB owns. |
| project_pi374_foreign_field_type | DELETE-DUP | PI-374 status — DB owns; re-audit-to-reclassify lesson splits to MIGRATE-DB. |
| project_pi051_rbac_security_salvage | MIGRATE-DB | Local-only branches + salvage state (LOCAL-ONLY branch tips) not in DB — state/lesson. |
| project_prj015_ui_usability_batch | DELETE-DUP | PRJ-015 status — DB owns. |
| project_prj027_multi_instance_audit | DELETE-DUP | PRJ-027 status — DB owns. |
| project_prj030_release_pipeline | DELETE-DUP | PRJ-030 status — DB owns; ANTHROPIC_API_KEY-in-env pointer → MIGRATE-PTR. |
| project_prj039_pipeline_hardening | DELETE-DUP | PRJ-039/040 status — DB owns. |
| project_prj041_agent_selection_observability | DELETE-DUP | PRJ-041 status — DB owns. |
| project_prj042_yaml_publish_validate | DELETE-DUP | PRJ-042 status — DB owns. |
| project_prj044_audit_progress | DELETE-DUP | PRJ-044 status — DB owns. |
| project_prj048_governance_enforcement_gate | DELETE-DUP | PRJ-048 status — DB owns. |
| project_ado_orchestration_driver | DELETE-DUP | PI-143 status — DB owns; the "won't adopt In-Progress phase" lesson splits to MIGRATE-DB. |
| project_coordinating_runtime_layer1 | DELETE-DUP | PI-132 status — DB owns; verify-by-result (DEC-396) is a DB decision. |
| project_coordinating_runtime_layer2 | DELETE-DUP | PI-139 status — DB owns. |
| project_agent_system_target_model | MIGRATE-PTR | Points at agent-PRD doc locations + which are built — a pointer + state. |
| project_realtime_agent_monitoring_plan | MIGRATE-DB | Planned-not-built design intent (next=REQ-277/TOP-100) — state. |
| project_engine_neutral_design_adapters | DELETE-DUP | PRJ-025 status — DB owns; YAML-out-CLI-only + Generate-UI-gap → MIGRATE-DB (state). |
| project_audit_roundtrip_completeness | DELETE-DUP | PRJ-024 status — DB owns; platform-blocked reqs are DB records. |
| project_audit_feature | STAYS-REPO | Planned feature description — architecture/feature reference. |
| project_stakeholder_portal | MIGRATE-DB | A decision (API-driven portal) — belongs as a DB decision. |
| project_v1_yaml_reconcile | MIGRATE-DB | Worktree/branch state + deferred scope — operational state. |
| project_entity_activity_panels | DELETE-DUP | PI-344 status — DB owns; verify-rendering-not-metadata lesson splits to MIGRATE-DB. |
| project_entity_option_reconcile | DELETE-DUP | PI-312/313 status — DB owns. |
| project_rel024_threeway_reconcile | DELETE-DUP | REL-024 planning status — DB owns. |
| project_rel027_reconcile_redesign | DELETE-DUP | REL-027 status (SHIPPED) — DB owns. |
| project_rel037_reconcile_ui_quick | DELETE-DUP | REL-037 status (SHIPPED) — DB owns; grab-the-lane monitor lesson splits to MIGRATE-DB. |
| project_rel038_audit_role_reconcile | MIGRATE-DB | Open defect + recovery steps (PI-352/353/354 Draft) — active state/lesson. |
| project_rel056_enum_option_reconcile | MIGRATE-DB | Off-pipeline-awaits-merge state + EspoCRM blank-option gotcha — state/lesson. |
| project_cbm_email_engine_fixes | DELETE-DUP | REL-036 status — DB owns; manual-mode-needs-human-signoff lesson splits to MIGRATE-DB. |
| project_cbm_form_gaps_and_cprefix_bug | DELETE-DUP | PI-307/309/300 status — DB owns; layout-API how-to splits to MIGRATE-DB. |
| project_cbm_pipeline_proof_slice1 | MIGRATE-DB | Proof-complete state + DEC-002 deploy-wizard defect lesson. |
| project_cbm_prod_full_structural_deploy | MIGRATE-DB | Deploy-complete state + "raw audit YAML not directly deployable" lesson. |
| project_phase15_cbm_first_run | MIGRATE-DB | E2E run state + "list endpoints ignore offset" lesson. |
| project_cbm_client_intake | MIGRATE-PTR | Pointer to a separate project/repo (cbm-client-intake). |
| project_req421_scan_local_skills | DELETE-DUP | PI-362 status (merged PR#18) — DB owns; restart-API-to-serve note → MIGRATE-DB (action). |

**CBM-scoped flag:** the `*_cbm_*` memories (7) are CBM-client knowledge; PI-356 should decide whether their home is ENG-001 or the CBM engagement's own store.

---

## Summary counts

| Destination | Global CLAUDE.md | Project CLAUDE.md (groups) | Memory files | 
|---|---|---|---|
| DELETE-DUP | 0 | ~1 large group | 34 |
| MIGRATE-DB | 0 | 5 groups | 32 |
| MIGRATE-PREF | 0 | (overlap) | 7 |
| MIGRATE-PTR | 0 | 1 | 5 |
| STAYS-REPO | 0 | ~9 groups | 3 |
| STAYS-BOOT | 1 | 1 (governance pointer) | 0 |

**Memory total: 91** (34 delete-dup + 32 migrate-db + 7 migrate-pref + 5 migrate-ptr + 3 stays-repo). Nothing unclassified.

## Key findings for the PI-356 design (the reuse-or-new decisions)

1. **Two new DB structures are implied:** a **preferences** home (7 interaction-style feedback items) and an **operational-lessons** home (the ~40 gotcha/how-to items split out of hybrids). Governance-rule feedback can reuse the existing `governance_rule` entity (TOP-013).
2. **Most `project_*` memories are DELETE-DUP hybrids** — the DB already owns the decision/PI/commit; only the welded *lesson* needs a home. The migration is mostly *deletion after confirmation*, not bulk insertion.
3. **The DB is unreachable at cold-session start** (cloud, auth-gated) — PI-358's bootstrap must degrade gracefully; a minimal STAYS-BOOT residual (read TOP-013 + the preferences/lessons records, with the API endpoint + a fallback) is unavoidable.
4. **Scope boundaries to resolve:** the global `~/.claude/CLAUDE.md` (no crmbuilder-DB home), the CBM-scoped memories (ENG-001 vs CBM engagement), and the large `STAYS-REPO` bulk of project `CLAUDE.md` (engine/schema/deploy reference that correctly stays).
