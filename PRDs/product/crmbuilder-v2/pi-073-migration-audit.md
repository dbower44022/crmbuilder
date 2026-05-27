# PI-073 Phase F — Data Migration Audit Report

**Generated:** 2026-05-27 13:09:06
**Phase:** F (data migration)
**Source DB:** branch isolation copy at `crmbuilder-v2/data/branch-pi-073/CRMBUILDER.db`

## Row counts

- legacy_conversations → new sessions: **66** rows migrated
- legacy_sessions → new conversations: **95** rows migrated

## Reference-edge retargeting

- `source_type_flipped_conv_to_sess`: 175
- `source_type_flipped_sess_to_conv`: 208
- `target_type_flipped_conv_to_sess`: 87
- `target_type_flipped_sess_to_conv`: 309
- `kind_renames_session_belongs_to_workstream`: 66
- `kind_renames_session_opens_against_work_ticket`: 54
- `kind_renames_session_follows_from`: 36
- `records_session_reversed`: 66

## legacy_conversations → sessions (CONV-NNN identifiers retained)

| Legacy identifier | New identifier | Legacy status | New status |
|---|---|---|---|
| CONV-001 | CONV-001 | complete | complete |
| CONV-002 | CONV-002 | complete | complete |
| CONV-003 | CONV-003 | complete | complete |
| CONV-004 | CONV-004 | complete | complete |
| CONV-005 | CONV-005 | complete | complete |
| CONV-006 | CONV-006 | complete | complete |
| CONV-007 | CONV-007 | complete | complete |
| CONV-008 | CONV-008 | complete | complete |
| CONV-009 | CONV-009 | complete | complete |
| CONV-010 | CONV-010 | complete | complete |
| CONV-011 | CONV-011 | complete | complete |
| CONV-012 | CONV-012 | complete | complete |
| CONV-013 | CONV-013 | complete | complete |
| CONV-014 | CONV-014 | complete | complete |
| CONV-015 | CONV-015 | complete | complete |
| CONV-016 | CONV-016 | complete | complete |
| CONV-017 | CONV-017 | complete | complete |
| CONV-018 | CONV-018 | complete | complete |
| CONV-019 | CONV-019 | complete | complete |
| CONV-020 | CONV-020 | complete | complete |
| CONV-021 | CONV-021 | complete | complete |
| CONV-022 | CONV-022 | complete | complete |
| CONV-023 | CONV-023 | complete | complete |
| CONV-024 | CONV-024 | complete | complete |
| CONV-025 | CONV-025 | complete | complete |
| CONV-026 | CONV-026 | complete | complete |
| CONV-027 | CONV-027 | complete | complete |
| CONV-028 | CONV-028 | complete | complete |
| CONV-029 | CONV-029 | complete | complete |
| CONV-030 | CONV-030 | complete | complete |
| CONV-031 | CONV-031 | complete | complete |
| CONV-032 | CONV-032 | complete | complete |
| CONV-033 | CONV-033 | complete | complete |
| CONV-034 | CONV-034 | complete | complete |
| CONV-035 | CONV-035 | complete | complete |
| CONV-036 | CONV-036 | complete | complete |
| CONV-037 | CONV-037 | complete | complete |
| CONV-038 | CONV-038 | complete | complete |
| CONV-039 | CONV-039 | complete | complete |
| CONV-040 | CONV-040 | complete | complete |
| CONV-041 | CONV-041 | complete | complete |
| CONV-042 | CONV-042 | complete | complete |
| CONV-043 | CONV-043 | complete | complete |
| CONV-044 | CONV-044 | complete | complete |
| CONV-045 | CONV-045 | complete | complete |
| CONV-046 | CONV-046 | complete | complete |
| CONV-047 | CONV-047 | complete | complete |
| CONV-048 | CONV-048 | complete | complete |
| CONV-049 | CONV-049 | complete | complete |
| CONV-050 | CONV-050 | complete | complete |
| CONV-051 | CONV-051 | complete | complete |
| CONV-052 | CONV-052 | complete | complete |
| CONV-053 | CONV-053 | complete | complete |
| CONV-054 | CONV-054 | complete | complete |
| CONV-055 | CONV-055 | complete | complete |
| CONV-056 | CONV-056 | complete | complete |
| CONV-057 | CONV-057 | complete | complete |
| CONV-058 | CONV-058 | complete | complete |
| CONV-059 | CONV-059 | complete | complete |
| CONV-060 | CONV-060 | complete | complete |
| CONV-061 | CONV-061 | complete | complete |
| CONV-062 | CONV-062 | complete | complete |
| CONV-063 | CONV-063 | complete | complete |
| CONV-064 | CONV-064 | complete | complete |
| CONV-065 | CONV-065 | complete | complete |
| CONV-066 | CONV-066 | complete | complete |

## legacy_sessions → conversations (SES-NNN identifiers retained)

| Legacy identifier | New identifier | Legacy status | New status |
|---|---|---|---|
| SES-001 | SES-001 | Complete | complete |
| SES-002 | SES-002 | Complete | complete |
| SES-003 | SES-003 | Complete | complete |
| SES-004 | SES-004 | Complete | complete |
| SES-005 | SES-005 | Complete | complete |
| SES-006 | SES-006 | Complete | complete |
| SES-007 | SES-007 | Complete | complete |
| SES-008 | SES-008 | Complete | complete |
| SES-009 | SES-009 | Complete | complete |
| SES-010 | SES-010 | Complete | complete |
| SES-011 | SES-011 | Complete | complete |
| SES-012 | SES-012 | Complete | complete |
| SES-013 | SES-013 | Complete | complete |
| SES-014 | SES-014 | Complete | complete |
| SES-015 | SES-015 | Complete | complete |
| SES-016 | SES-016 | Complete | complete |
| SES-017 | SES-017 | Complete | complete |
| SES-018 | SES-018 | Complete | complete |
| SES-019 | SES-019 | Complete | complete |
| SES-020 | SES-020 | Complete | complete |
| SES-021 | SES-021 | Complete | complete |
| SES-022 | SES-022 | Complete | complete |
| SES-023 | SES-023 | Complete | complete |
| SES-024 | SES-024 | Complete | complete |
| SES-025 | SES-025 | Complete | complete |
| SES-026 | SES-026 | Complete | complete |
| SES-027 | SES-027 | Complete | complete |
| SES-029 | SES-029 | Complete | complete |
| SES-030 | SES-030 | Complete | complete |
| SES-031 | SES-031 | Complete | complete |
| SES-032 | SES-032 | Complete | complete |
| SES-033 | SES-033 | Complete | complete |
| SES-034 | SES-034 | Complete | complete |
| SES-035 | SES-035 | Complete | complete |
| SES-036 | SES-036 | Complete | complete |
| SES-037 | SES-037 | Complete | complete |
| SES-038 | SES-038 | Complete | complete |
| SES-039 | SES-039 | Complete | complete |
| SES-040 | SES-040 | Complete | complete |
| SES-041 | SES-041 | Complete | complete |
| SES-042 | SES-042 | Complete | complete |
| SES-043 | SES-043 | Complete | complete |
| SES-044 | SES-044 | Complete | complete |
| SES-045 | SES-045 | Complete | complete |
| SES-046 | SES-046 | Complete | complete |
| SES-047 | SES-047 | Complete | complete |
| SES-048 | SES-048 | Complete | complete |
| SES-049 | SES-049 | Complete | complete |
| SES-050 | SES-050 | Complete | complete |
| SES-051 | SES-051 | Complete | complete |
| SES-052 | SES-052 | Complete | complete |
| SES-053 | SES-053 | Complete | complete |
| SES-054 | SES-054 | Complete | complete |
| SES-055 | SES-055 | Complete | complete |
| SES-056 | SES-056 | Complete | complete |
| SES-057 | SES-057 | Complete | complete |
| SES-058 | SES-058 | Complete | complete |
| SES-059 | SES-059 | Complete | complete |
| SES-060 | SES-060 | Complete | complete |
| SES-061 | SES-061 | Complete | complete |
| SES-062 | SES-062 | Complete | complete |
| SES-063 | SES-063 | Complete | complete |
| SES-064 | SES-064 | Complete | complete |
| SES-065 | SES-065 | Complete | complete |
| SES-066 | SES-066 | Complete | complete |
| SES-067 | SES-067 | Complete | complete |
| SES-068 | SES-068 | Complete | complete |
| SES-069 | SES-069 | Complete | complete |
| SES-070 | SES-070 | Complete | complete |
| SES-071 | SES-071 | Complete | complete |
| SES-072 | SES-072 | Complete | complete |
| SES-073 | SES-073 | Complete | complete |
| SES-074 | SES-074 | Complete | complete |
| SES-075 | SES-075 | Complete | complete |
| SES-076 | SES-076 | Complete | complete |
| SES-077 | SES-077 | Complete | complete |
| SES-078 | SES-078 | Complete | complete |
| SES-079 | SES-079 | Complete | complete |
| SES-080 | SES-080 | Complete | complete |
| SES-081 | SES-081 | Complete | complete |
| SES-082 | SES-082 | Complete | complete |
| SES-083 | SES-083 | Complete | complete |
| SES-084 | SES-084 | Complete | complete |
| SES-085 | SES-085 | Complete | complete |
| SES-086 | SES-086 | Complete | complete |
| SES-087 | SES-087 | Complete | complete |
| SES-088 | SES-088 | Complete | complete |
| SES-089 | SES-089 | Complete | complete |
| SES-090 | SES-090 | Complete | complete |
| SES-091 | SES-091 | Complete | complete |
| SES-092 | SES-092 | Complete | complete |
| SES-093 | SES-093 | Complete | complete |
| SES-094 | SES-094 | Complete | complete |
| SES-095 | SES-095 | Complete | complete |
| SES-096 | SES-096 | Complete | complete |
