# PI-509 disposition: the three record types no code creates

| Field | Value |
|---|---|
| Title | PI-509 disposition: the three record types no code creates |
| Last Updated | 09-15-26 00:39 |
| Revision | 1.0 |
| Status | Final |
| Source | PI-509 / REQ-601 / DEC-1089 |

## What was found

The record-type-to-segment map (revision 1.0) marked three record types as removal candidates because no operation creates them. This lane confirmed it by reading, not by name: a search of every repository, router, adapter, transform, connector tool, desktop screen and test for the three class names and the three table names found the model classes, one entity-summary entry, two trunk migration revisions that create the tables, and tests of those. Nothing inserts a row.

The live store was read on 09-15-26 (read-only, by the session lead): `services` 0 rows, `source_mapping_joins` 0 rows, `field_mapping_translations` 0 rows. No foreign key points into any of the three.

## What was removed

| Where | What |
|---|---|
| Record definitions | The classes Service, SourceMappingJoin and FieldMappingTranslation, and the two vocabulary imports only they used. Tables 111 to 108. |
| Vocabulary | The entity type `service`; the reference kinds `process_consumes_service` and `service_owns_entity` and their pair rules; `service` as a source of `rejected_by_decision`; the status set and transitions for services; the translation-type set. The reference-pointer kind `service` is a different concept and stays. |
| Entity summary | The `service` entry. |
| Tests | The service model test and the service vocabulary test are deleted. The source-mapping shape test now expects five tables. The drift-safety tests no longer pin the fork revision as the build head. |

## What was kept, and why

The change-log check keeps `service` admissible. The change log is history, and rows written while the type existed are never deleted, so the vocabulary's change-log set carries the retired type with a comment saying so.

The two trunk revisions that created the tables (0014 and 0038) still create them, from frozen definitions in `crmbuilder_v2/migration/retired_tables.py`, so a store walked through the trunk behaves as it always did. Revision 0014 also keeps admitting the retired type and kinds in the checks it rebuilds, as it did on the day it shipped (lesson LSN-062); the shared_core branch narrows them later.

## The migrations, one per owning branch

| Branch | Revision | Effect |
|---|---|---|
| solution_design | `solution_design_0002_drop_services` | Drops `services`; downgrade recreates it. |
| build | `build_0002_drop_orphan_mapping_tables` | Drops `source_mapping_joins` and `field_mapping_translations`; downgrade recreates both. |
| shared_core | `shared_core_0002_retire_service_reference_type` | Narrows the three `refs` checks to the live vocabulary. Refuses, changing nothing, if any reference row still names the retired type or kinds, so a rehearsal on a clone of the live store surfaces such rows for the product owner. Downgrade widens the checks again. |

The third revision was needed because `service` was a reference entity type and `refs` is a Shared Core table; a revision touches only its owner's tables.

## Rehearsal

Not run by this lane (no access to the live store by directive). Required before deploy: dump, restore into the dev container as a separate database, `upgrade heads`, confirm the three tables are gone and the shared_core revision did not refuse.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-15-26 00:39 | Claude (Claude Code, PI-509 lane) | Written with the build. |
