# PI-503 — migration-test disposition after the SQLite chain removal

Last Updated: 09-14-26 01:41 · Revision 1.0 — see change log at the end.

**Planning item:** PI-503 · **Requirement:** REQ-593 · **Decision:** DEC-1082 (migration tests run only against Postgres)

## What changed

The SQLite Alembic chain (`crmbuilder-v2/migrations/`, 139 revisions, its `env.py`, the root
`crmbuilder-v2/alembic.ini` and the deferred SQLite-only migration) is removed. The Postgres
tree at `crmbuilder-v2/migrations/pg/` is the only chain. `crmbuilder-v2-bootstrap-db` and
`crmbuilder-v2-api` refuse a SQLite URL with a message naming the local dev container
(`crmb_pg_dev`, `crmbuilder-v2/docker-compose.dev.yml`, port 55432). The everyday test
suite is untouched: its per-test SQLite files are built from the models with `create_all`
and never ran a chain.

Forty-nine test files mentioned Alembic before the change, and three more called
`bootstrap_database` on a SQLite file. Each is listed below with its disposition: **retargeted** (now exercises the corresponding Postgres revision),
**dropped** (with the reason), **unaffected (adjusted)** (not a chain test, but touched
`bootstrap_database`, which now refuses SQLite) or **unaffected**.

Summary: retargeted 34 · dropped 11 · unaffected (adjusted) 3 · unaffected 5.

## How a retargeted test runs

`tests/crmbuilder_v2/migration/_pg_chain.py` is the shared helper:

- `requires_postgres` skips the test unless `CRMBUILDER_V2_TEST_PG_URL` is set.
- `fresh_db()` works in a sibling database `<name>_migrations` on the same server, created
  on demand and wiped (`DROP SCHEMA public CASCADE`) before each test, so the churn never
  touches the suite's shared schema. It pre-creates `alembic_version` with a
  `VARCHAR(255)` column: Alembic creates it as `VARCHAR(32)` and forty of this chain's
  revision ids are longer (Postgres enforces the length; SQLite did not).
- Test connections carry `session_replication_role=replica` (foreign-key triggers off),
  the posture the SQLite-file tests had by default; the `alembic` subprocess strips it and
  runs the chain as production does.
- The pattern is unchanged: `create_all` (head shape), `stamp`, real `downgrade`, real
  `upgrade`, assert. The Postgres baseline is itself `create_all`, so a from-base
  `upgrade` to an intermediate revision is not possible on this chain.

Each retargeted file is renamed after the Postgres revision it exercises (the SQLite
number it carried is gone with the chain); test function names inside the files keep
their historical wording.

## Disposition

| Test file (name before the change) | Disposition | Reason / note |
|---|---|---|
| `test_0041_principals_tokens_roles.py` | retargeted | now `test_0003_principals_tokens_roles.py`, exercises Postgres revision `0003_pi_gamma_principals_tokens_roles`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0042_changelog_principal_attribution.py` | retargeted | now `test_0004_changelog_principal_attribution.py`, exercises Postgres revision `0004_pi_gamma_changelog_principal_attribution`. |
| `test_0045_findings_entity.py` | retargeted | now `test_0007_findings_entity.py`, exercises Postgres revision `0007_pi_134_findings_entity`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0046_0047_pi_153_deposit_path.py` | retargeted | now `test_0009_pi_153_deposit_path.py`, exercises Postgres revision `0009_wtk_089_deposit_event_kind`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). Pre-state DDL ported: DATETIME to TIMESTAMP, GLOB to a regex CHECK. |
| `test_0048_migration_mapping_entity.py` | retargeted | now `test_0010_migration_mapping_entity.py`, exercises Postgres revision `0010_wtk_106_migration_mapping_entity`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0049_requirements_provenance.py` | retargeted | now `test_0011_requirements_provenance.py`, exercises Postgres revision `0011_requirements_provenance`. |
| `test_0050_planning_item_implements_requirement.py` | retargeted | now `test_0012_planning_item_implements_requirement.py`, exercises Postgres revision `0012_planning_item_implements_requirement`. |
| `test_0051_review_signoffs.py` | retargeted | now `test_0013_review_signoffs.py`, exercises Postgres revision `0013_review_signoffs`. |
| `test_0052_service_entity.py` | retargeted | now `test_0014_service_entity.py`, exercises Postgres revision `0014_pi_161_service_entity`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0053_execution_mode.py` | retargeted | now `test_0015_execution_mode.py`, exercises Postgres revision `0015_pi_183_execution_mode`. |
| `test_0059_instance_membership.py` | retargeted | now `test_0017_instance_membership.py`, exercises Postgres revision `0017_pi_185_instance_membership`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). CHECK presence read via reflection instead of sqlite_master. |
| `test_0060_layout_role_team.py` | retargeted | now `test_0018_layout_role_team.py`, exercises Postgres revision `0018_pi_193_194_layout_role_team`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0061_filtered_tab.py` | retargeted | now `test_0019_filtered_tab.py`, exercises Postgres revision `0019_pi_195_filtered_tab`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0081_source_mapping_tables.py` | retargeted | now `test_0038_source_mapping_tables.py`, exercises Postgres revision `0038_pi_255_source_mapping_tables`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0082_pipeline_events.py` | retargeted | now `test_0039_pipeline_events.py`, exercises Postgres revision `0039_pi_273_pipeline_events`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0083_agent_technology.py` | retargeted | now `test_0040_agent_technology.py`, exercises Postgres revision `0040_pi_271_agent_technology`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0084_pi_297_entity_tracks_activities.py` | retargeted | now `test_0041_pi_297_entity_tracks_activities.py`, exercises Postgres revision `0041_pi_297_entity_tracks_activities`. |
| `test_0085_agent_capability_description.py` | retargeted | now `test_0042_agent_capability_description.py`, exercises Postgres revision `0042_pi_301_agent_capability_description`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0086_security_rules.py` | retargeted | now `test_0043_security_rules.py`, exercises Postgres revision `0043_pi_051_security_rules`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). Boolean literals 0/1 became false/true. |
| `test_0087_work_task_resolved_agent_profile.py` | retargeted | now `test_0044_work_task_resolved_agent_profile.py`, exercises Postgres revision `0044_pi_302_work_task_resolved_agent_profile`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0088_task_transitions.py` | retargeted | now `test_0045_task_transitions.py`, exercises Postgres revision `0045_pi_304_task_transitions`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0089_pi_300_entity_collection_settings.py` | retargeted | now `test_0046_pi_300_entity_collection_settings.py`, exercises Postgres revision `0046_pi_300_entity_collection_settings`. |
| `test_0093_release_runs.py` | retargeted | now `test_0050_release_runs.py`, exercises Postgres revision `0050_pi_326_release_runs`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0096_association_mappings.py` | retargeted | now `test_0053_association_mappings.py`, exercises Postgres revision `0053_pi_255_association_mappings`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0123_deploy_runs.py` | retargeted | now `test_0080_deploy_runs.py`, exercises Postgres revision `0080_pi_419_deploy_runs`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). CHECK presence read via reflection instead of sqlite_master. |
| `test_0125_rule_audience_moment.py` | retargeted | now `test_0082_rule_audience_moment.py`, exercises Postgres revision `0082_pi_438_rule_audience_moment`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0127_rule_enforcement_overrides.py` | retargeted | now `test_0084_rule_enforcement_overrides.py`, exercises Postgres revision `0084_pi_439_rule_enforcement_overrides`. |
| `test_0130_field_vocabulary_subtractive.py` | retargeted | now `test_0087_field_vocabulary_subtractive.py`, exercises Postgres revision `0087_pi_414_field_vocabulary_subtractive`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0136_active_subset.py` | retargeted | now `test_0093_active_subset.py`, exercises Postgres revision `0093_pi_407_active_subset`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). Boolean literals 0/1 became false/true. |
| `test_0138_withdraws_and_claude_code.py` | retargeted | now `test_0095_withdraws_and_claude_code.py`, exercises Postgres revision `0095_pi_462_withdraws_and_claude_code`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0139_session_opening_fields.py` | retargeted | now `test_0096_session_opening_fields.py`, exercises Postgres revision `0096_pi_488_session_opening_fields`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_0140_transitions.py` | retargeted | now `test_0097_transitions.py`, exercises Postgres revision `0097_pi_471_transitions`. FK triggers off on test connections (was PRAGMA foreign_keys=OFF). |
| `test_pi308_drift_safety.py` | retargeted | bootstrap, drift gate and run_api refusal on Postgres; the SQLite-facing parts now assert the SqliteRefusedError and the message naming the dev container |
| `test_single_head.py` | retargeted | walks the Postgres chain only; the SQLite chain entry is gone |
| `test_0012_commits_and_blocked_by.py` | dropped | SQLite revision 0012 predates the Postgres baseline (0001_pg_baseline materialises the models); its shape is in the baseline and has no revision to round-trip |
| `test_0037_engagements_table.py` | dropped | SQLite revisions 0037 predate the Postgres baseline; the engagements table is part of the baseline |
| `test_0038_engagement_id_discriminator.py` | dropped | SQLite revision 0038 predates the Postgres baseline; the discriminator is part of the baseline |
| `test_0043_registry_catalog.py` | dropped | Postgres 0005's downgrade drops agent_profiles, which 0065 (agent_profile_bindings) references; from a head-shaped schema Postgres refuses the drop (DependentObjectsStillExist). Only SQLite's lax DROP let the SQLite test pass. The revision's downgrade is unreachable on the live chain. |
| `test_0054_instance_entity.py` | dropped | Postgres 0016's downgrade drops instances, which later revisions reference (memberships, deploy configs, publish runs); same DependentObjectsStillExist as 0043 |
| `test_0055_field_entity_intrinsic.py` | dropped | SQLite revision 0055 (PI-182) has no Postgres counterpart; its columns are in the baseline |
| `test_0056_composite_design_records.py` | dropped | SQLite revision 0056 (PI-189) has no Postgres counterpart; the tables are in the baseline |
| `test_0057_condition_design_records.py` | dropped | SQLite revision 0057 (PI-189) has no Postgres counterpart; the tables are in the baseline |
| `test_0058_dedup_template_design_records.py` | dropped | SQLite revision 0058 (PI-189) has no Postgres counterpart; the tables are in the baseline |
| `test_0062_field_derived_formula.py` | dropped | SQLite revision 0062 (PI-197) has no Postgres counterpart; the columns are in the baseline |
| `test_catalog_seed_migration.py` | dropped | ran the SQLite chain from base to exercise the 0004 catalog-seed migration; the Postgres chain has no seed migration (its baseline is create_all) and the test was already permanently skipped since the catalog YAMLs were decommissioned |
| `conftest.py` | unaffected (adjusted) | the SQLite branch builds the per-test file with create_all and no longer stamps it; the Postgres branch (CRMBUILDER_V2_TEST_PG_URL) is unchanged |
| `test_engagement_leak_isolation.py` | unaffected (adjusted) | not a chain test; it bootstrapped its own SQLite file via bootstrap_database, which now refuses SQLite, so it builds the file from the models like the fixture does |
| `test_engagement_scope_middleware.py` | unaffected (adjusted) | same as test_engagement_leak_isolation: bootstrap_database replaced by create_all for its per-test SQLite file |
| `test_knowledge_structures.py` | unaffected | mentions alembic only in a lesson body used as test data |
| `test_migration_lock.py` | unaffected | the scheduler's migration lock; no chain is run |
| `test_registry_catalog.py` | unaffected | mentions alembic only in a rule predicate used as test data |
| `test_rule_check.py` | unaffected | mentions alembic only in a forbidden-command pattern used as test data |
| `test_sqlite_to_postgres.py` | unaffected | the cutover copier; already Postgres, no chain is run |

## Measured runtime

| Run | Tests | Wall time | Notes |
|---|---|---|---|
| `tests/crmbuilder_v2/migration/` on Postgres, dev container with `fsync=off` | 71 passed | 130.2 s | local machine, container from `docker-compose.dev.yml`; ~1.8 s per test, dominated by the per-test `DROP SCHEMA` + `create_all` of 117 tables |
| same directory before the container ran with `fsync=off` (partial, earlier iteration) | 58 run | 309.0 s | ~5 s per test spent in `DataFileImmediateSync`; the reason `docker-compose.dev.yml` now passes `-c fsync=off -c synchronous_commit=off -c full_page_writes=off` (ephemeral dev data) |
| same directory with `CRMBUILDER_V2_TEST_PG_URL` unset | 21 passed, 50 skipped | 24.8 s | the chain tests skip; the 21 are the non-chain tests in the directory |
| full `tests/crmbuilder_v2` suite, SQLite mode (`CRMBUILDER_V2_TEST_PG_URL` unset), branch pi-503 | 6102 passed, 3 failed, 51 skipped, 5 xfailed | 4244 s (1:10:44) | the 3 failures are `tests/crmbuilder_v2/scripts/test_closeout_validator.py` expecting `session_medium='claude_code'` to be rejected; the vocabulary has admitted it since PI-462 (2026-09-04) and neither the validator, its test nor the vocabulary differs from `origin/main` on this branch — pre-existing, not caused by PI-503 |

## Findings outside this planning item's scope

- **A fresh Postgres bootstrapped by `bootstrap_database` gets a 32-character version
  column.** `create_all` + `stamp head` leaves `alembic_version.version_num` as Alembic's
  default `VARCHAR(32)`. The current head (`0097_pi_471_transitions`) fits, but the next
  revision id longer than 32 characters (forty existing ones are) will fail its
  `upgrade` on any store bootstrapped that way. The live store evidently has a wider
  column (it has applied `0096_pi_488_session_opening_fields`, 34 characters). Worth a
  planning item: widen the column in `bootstrap_database`, or cap revision ids at 32.
- **`make_alembic_config` passes the URL through `configparser` interpolation.** A URL
  containing `%` (an encoded password, or the test-only `options` parameter) raises
  `invalid interpolation syntax`. Pre-existing; the tests avoid it by handing the
  application a plain URL.
- **Two Postgres downgrades are unreachable from a head-shaped schema** (revisions 0005 and
  0016 drop tables later revisions reference). Their tests are dropped rather than
  rewritten; if a rollback across those revisions is ever needed, the downgrades need
  `CASCADE` or explicit dependent handling first.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-14-26 01:41 | Claude (Claude Code, PI-503 lane) | First version, written with the build. |
