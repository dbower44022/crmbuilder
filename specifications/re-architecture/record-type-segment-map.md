# Record-type-to-segment map
| Field | Value |
|---|---|
| Title | Record-type-to-segment map |
| Last Updated | 09-15-26 00:39 |
| Revision | 1.1 |
| Status | Approved by the product owner, 09-14-26, segment by segment in session SES-414 |
| Source | PI-504 / REQ-588 / DEC-1077 / DEC-1086; removals PI-509 / REQ-601 |

## Purpose

Every record type in the V2 store is assigned to exactly one of the seven functional segments approved in DEC-1077, or to the shared core plumbing. The seven segments are Client Management; Discovery and Requirements; Solution Design; Build; Operate; CRMBuilder Delivery; and Shared Core. The shared core plumbing is the engagement-scope filter and base table shape, identifier reservation, the reference graph and its vocabulary, the change log, secrets, and the authentication check.

The ownership rule is fixed: the segment whose operation creates a record owns it. Other segments read it. Addendum approved in DEC-1086: a record type that more than one segment creates is cross-segment and lives in the Shared Core; reading alone does not make a record cross-segment. The Shared Core holds three families: the shared plumbing, the governance records, and the cross-segment filing concepts (topics, terms). Where a record is read by other segments, the Readers column names them, so a later package move knows which contracts it must keep.

This document is the work order for every move of code into a segment package. Until the product owner approves it, no record type moves.

## Method

The table classes were enumerated from the access-layer models module. There are 117 classes. Six are not record types (four constraint helpers, the declarative base, and the primary-key mixin); they are listed in the appendix. The remaining 111 are record types and appear once each below.

For each record type the creating operation was found by locating every call that constructs the class outside the models module, in the repositories, the access-layer modules, the API routers, the desktop application, the introspection package and the scheduler. Placement was derived from that creating operation and from the repository's own statement of what the record is, not from the class name. Where the creating operation sits in a router or screen rather than a repository, the row names both.

Confidence is `verified` when the creating operation was read and its statement of purpose settles the segment. It is `inferred` when the creating operation was read but the segment still rests on judgement, or when no creating operation exists. Every inferred row appears again under Open placements.

## Counts per segment

| Segment | Record types |
|---|---|
| Client Management | 5 |
| Discovery and Requirements | 8 |
| Solution Design | 30 |
| Build | 14 |
| Operate | 4 |
| CRMBuilder Delivery | 23 |
| Shared Core | 20 |
| Shared core plumbing | 4 |
| Total | 108 |

## The mapping

### Client Management

| Class | Table name | Owning segment | Creating operation | Evidence | Confidence | Readers |
|---|---|---|---|---|---|---|
| EngagementRow | engagements | Client Management | access/engagement.py:_new_row | The engagement registry row that every scope resolver reads; created by the engagement repository. | verified | all segments (scope) |
| PrincipalRow | principals | Client Management | access/principal.py:create_principal | A human or service identity; created by the identity repository behind the authentication chokepoint. | verified | shared core (authentication) |
| ApiTokenRow | api_tokens | Client Management | access/principal.py:mint_token | An access token minted for a principal. | verified | shared core (authentication) |
| RoleAssignmentRow | role_assignments | Client Management | access/principal.py:assign_role | Grants a principal a role on an engagement. | verified | shared core (authentication) |
| Participant | participants | Client Management | access/repositories/participant.py:_new_participant_row | The real engagement person or role (consultant, client expert) that a persona is backed by. | verified | Discovery and Requirements (persona backing) |

### Discovery and Requirements

| Class | Table name | Owning segment | Creating operation | Evidence | Confidence | Readers |
|---|---|---|---|---|---|---|
| Charter | charter | Discovery and Requirements | access/repositories/charter.py:replace | The engagement's charter document, versioned; the Project Definition deliverable. | verified | Shared Core |
| Domain | domains | Discovery and Requirements | access/repositories/domain.py:_new_domain_row | A Phase 1 domain inventory member, the first methodology entity type. | verified | Solution Design |
| Persona | personas | Discovery and Requirements | access/repositories/persona.py:_new_persona_row | A methodology persona captured during discovery. | verified | Solution Design |
| Process | processes | Discovery and Requirements | access/repositories/process.py:_new_process_row | A business process captured one conversation at a time (kind of work: define new business processes). | verified | Solution Design, Shared Core (catalogue of kinds of work) |
| Transition | transitions | Discovery and Requirements | access/repositories/transition.py:_new_row | One allowed status move within a process; created with the process. | verified | Solution Design |
| Requirement | requirements | Discovery and Requirements | access/repositories/requirement.py:_new_requirement_row | A requirement elicited from the client; confirmed only through an approving decision. | verified | Solution Design, Shared Core, CRMBuilder Delivery (release scope) |
| ReviewSignoff | review_signoffs | Discovery and Requirements | access/repositories/review_signoffs.py:create | The recorded attestation that a topic's requirements were reviewed; snapshots the requirement set. | verified | Shared Core |
| ReferenceEntry | reference_entries | Discovery and Requirements | access/repositories/reference_entries.py:_new_row | Cross-engagement client-industry knowledge for the discovery phase (domain knowledge, organisation structure, inventory items). | verified | none |

### Solution Design

| Class | Table name | Owning segment | Creating operation | Evidence | Confidence | Readers |
|---|---|---|---|---|---|---|
| Entity | entities | Solution Design | access/repositories/entity.py:_new_entity_row | An engine-neutral design entity. | verified | Build, Operate |
| Field | fields | Solution Design | access/repositories/field.py:_new_field_row | A field on a design entity. | verified | Build |
| FieldOption | field_options | Solution Design | access/repositories/field.py:_replace_options | An enumeration option of a field; written with the field. | verified | Build |
| Association | associations | Solution Design | access/repositories/association.py:_new_row | An engine-neutral entity-to-entity link. | verified | Build |
| Rule | rules | Solution Design | access/repositories/rule.py:_new_row | A condition-carrying rule on a field or entity. | verified | Build |
| FieldPermissionRule | field_permission_rules | Solution Design | access/repositories/field_permission_rule.py:_new_row | A role's access level to one field. | verified | Build |
| FieldVisibilityRule | field_visibility_rules | Solution Design | access/repositories/field_visibility_rule.py:_new_row | One (role, field) visibility decision. | verified | Build |
| View | views | Solution Design | access/repositories/view.py:_new_row | An engine-neutral list view. | verified | Build |
| Automation | automations | Solution Design | access/repositories/automation.py:_new_row | An engine-neutral workflow on one entity. | verified | Build |
| DedupRule | dedup_rules | Solution Design | access/repositories/dedup_rule.py:_new_row | An engine-neutral duplicate-detection rule. | verified | Build |
| MessageTemplate | message_templates | Solution Design | access/repositories/message_template.py:_new_row | An engine-neutral notification template. | verified | Build |
| Layout | layouts | Solution Design | access/repositories/layouts.py:_new_row | An engine-neutral layout of an entity. | verified | Build |
| Role | roles | Solution Design | access/repositories/roles.py:_new_row | An engine-neutral security role. | verified | Build |
| Team | teams | Solution Design | access/repositories/teams.py:_new_row | An engine-neutral security team. | verified | Build |
| FilteredTab | filtered_tabs | Solution Design | access/repositories/filtered_tabs.py:_new_row | An engine-neutral entity-bound filter view. | verified | Build |
| EngineOverride | engine_overrides | Solution Design | access/repositories/engine_override.py:_new_row | A per-engine rendering adjustment for one design construct. | verified | Build |
| SystemSetting | system_settings | Solution Design | access/repositories/system_settings.py:_new_row | The one design construct whose value is per instance; the setting itself is design. | verified | Build |
| TestSpec | test_specs | Solution Design | access/repositories/test_spec.py:_new_test_spec_row | A test specification authored against the design; Build records runs against it through the record_run helper. | verified | Build (records runs) |
| CrmCandidate | crm_candidates | Solution Design | access/repositories/crm_candidate.py:_new_crm_candidate_row | A Phase 1 CRM candidate: the buy, adopt or build analysis input. | verified | Discovery and Requirements |
| Service | services | Solution Design | none found | A cross-domain service in the target system (document storage, notification). No repository, router or other writer constructs this row today. | removed (PI-509) | none |
| MigrationMapping | migration_mappings | Solution Design | access/repositories/migration_mapping.py:_new_row | One keep or transform disposition's data-migration obligation from a source entity or field to target fields, with transform rules; a design-time statement consumed by a compiler. | approved | Build |
| CatalogEntity | catalog_entity | Solution Design | access/repositories/catalog/write.py:create_entity | The base-entity catalogue used by the design gap check; system-wide, seeded by the bootstrap loader. | verified | none |
| CatalogEntitySynonym | catalog_entity_synonym | Solution Design | access/repositories/catalog/write.py:_replace_entity_children | Child of a catalogue entity, written with it. | verified | none |
| CatalogEntitySystem | catalog_entity_system | Solution Design | access/repositories/catalog/write.py:_replace_entity_children | Child of a catalogue entity, written with it. | verified | none |
| CatalogSource | catalog_source | Solution Design | access/repositories/catalog/write.py:_replace_entity_children | Child of a catalogue entity, written with it. | verified | none |
| CatalogAttribute | catalog_attribute | Solution Design | access/repositories/catalog/write.py:create_attribute | An attribute of a catalogue entity. | verified | none |
| CatalogAttributeEnumValue | catalog_attribute_enum_value | Solution Design | access/repositories/catalog/write.py:_replace_attribute_children | Child of a catalogue attribute, written with it. | verified | none |
| CatalogAttributeSynonym | catalog_attribute_synonym | Solution Design | access/repositories/catalog/write.py:_replace_attribute_children | Child of a catalogue attribute, written with it. | verified | none |
| CatalogAttributePresence | catalog_attribute_presence | Solution Design | access/repositories/catalog/write.py:_replace_attribute_children | Child of a catalogue attribute, written with it. | verified | none |
| CatalogRelationship | catalog_relationship | Solution Design | access/repositories/catalog/write.py:_replace_outbound_relationships | A relationship between catalogue entities. | verified | none |
| CatalogRelationshipPresence | catalog_relationship_presence | Solution Design | access/repositories/catalog/write.py:_replace_outbound_relationships | Child of a catalogue relationship, written with it. | verified | none |

### Build

| Class | Table name | Owning segment | Creating operation | Evidence | Confidence | Readers |
|---|---|---|---|---|---|---|
| PublishRun | publish_runs | Build | access/repositories/publish_runs.py:create_publish_run | The operational log of one publish of the design to a target instance. | verified | Operate |
| AuditRun | audit_runs | Build | access/repositories/audit_runs.py:create_audit_run | The job record of one audit of an instance. | verified | none |
| ReconcileTransaction | reconcile_transactions | Build | access/repositories/reconcile_transactions.py:record | The append-only trail of every reconcile action against an instance. | verified | none |
| InstanceMembership | instance_memberships | Build | introspect/entity_audit.py and access/reconcile_apply.py via access/repositories/instance_membership.py:upsert_membership | Whether a design object is present on an instance; written by the audit and by reconcile apply. | verified | Operate, Solution Design |
| UtilizationEvidence | utilization_evidence | Build | access/repositories/utilization_evidence.py:create_utilization_evidence | One profiling measurement from the audit's record-utilization profiler. | verified | Discovery and Requirements |
| MappingCandidate | mapping_candidates | Build | access/repositories/mapping_candidate.py:_new_row | An unmatched source object surfaced by an audit; the reconciler writes here, never to the mapping tables. | verified | none |
| ManualConfig | manual_configs | Build | api/routers/manual_configs.py via access/repositories/manual_config.py:_new_manual_config_row | One item the operator must configure by hand in the live CRM platform after publish. | approved | Operate |
| SystemSettingValue | system_setting_values | Build | api/routers/system_settings.py:set_value via access/repositories/system_settings.py:set_value | The value one instance is declared to hold for a setting; the audit compares its reading against it. | approved | Operate, Solution Design |
| ConformanceOverride | conformance_overrides | Build | api/routers/instances.py via access/repositories/conformance_overrides.py:create_override | An operator authorisation for one publish to proceed past a blocking conformance result; consumed once. | approved | none |
| SourceMapping | source_mappings | Build | ui/dialogs/candidate_resolve.py via access/repositories/source_mapping.py:create_source_mapping | A human resolves a mapping candidate into an entity-level mapping from a discovered source entity to the design; created from the reconcile screens. | approved | Solution Design |
| SourceMappingTarget | source_mapping_targets | Build | access/repositories/source_mapping_targets.py:add_target | A design-entity target of a source mapping; written with it. | approved | Solution Design |
| SourceMappingJoin | source_mapping_joins | Build | none found | Child of a source mapping. No writer constructs this row today; placement follows its parent. | removed (PI-509) | Solution Design |
| FieldMapping | field_mappings | Build | ui/dialogs/candidate_resolve.py via access/repositories/field_mapping.py:create_field_mapping | A field-level mapping decision under a source mapping. | approved | Solution Design |
| FieldMappingTranslation | field_mapping_translations | Build | none found | Child of a field mapping. No writer constructs this row today; placement follows its parent. | removed (PI-509) | Solution Design |
| AssociationMapping | association_mappings | Build | access/repositories/association_mapping.py:create_association_mapping | A relationship-level mapping from a discovered source relationship to a design association. | approved | Solution Design |
| ValueMapping | value_mappings | Build | access/repositories/value_mapping.py:create_value_mapping | A value-level mapping decision for one source enumeration value. | approved | Solution Design |

### Operate

| Class | Table name | Owning segment | Creating operation | Evidence | Confidence | Readers |
|---|---|---|---|---|---|---|
| Instance | instances | Operate | access/repositories/instances.py:_new_row | One connection to a live CRM system; created when a server is provisioned or an existing system is connected. | verified | Build, Solution Design |
| InstanceDeployConfig | instance_deploy_configs | Operate | access/repositories/instance_deploy_config.py:upsert_deploy_config | The one-to-one deployment configuration of an instance. | verified | none |
| ProviderCredential | provider_credentials | Operate | access/repositories/provider_credentials.py:upsert_provider_credential | An engagement's token for an infrastructure provider, held as an opaque secret reference. | verified | shared core (secrets) |
| DeployRun | deploy_runs | Operate | access/repositories/deploy_runs.py:create_deploy_run | The operational log of one provisioning job. | verified | none |

### CRMBuilder Delivery

| Class | Table name | Owning segment | Creating operation | Evidence | Confidence | Readers |
|---|---|---|---|---|---|---|
| Workstream | workstreams | CRMBuilder Delivery | access/repositories/workstreams.py:_new_row | A single delivery phase of one planning item in the agent delivery organisation. | verified | Shared Core |
| WorkTask | work_tasks | CRMBuilder Delivery | access/repositories/work_tasks.py:_new_row | The single-area, agent-claimable unit of execution within a workstream. | verified | Shared Core |
| TaskTransitionRow | task_transitions | CRMBuilder Delivery | access/repositories/task_transitions.py:record | Append-only log of every work task status change; the scheduler is the sole writer. | verified | none |
| EngagementArea | engagement_areas | CRMBuilder Delivery | access/repositories/engagement_areas.py:create_engagement_area | A user-defined work-area label; the engagement tier of the two-tier area model that work tasks carry. | verified | none |
| AreaSpec | area_specs | CRMBuilder Delivery | access/repositories/area_specs.py:author_spec | The per-release, per-area implementation and testable specification an area architect authors. | verified | none |
| AreaReopen | area_reopens | CRMBuilder Delivery | access/reopen.py:reopen_area | The in-lane reopen of a frozen area during a release. | verified | none |
| PlanningAreaClaim | planning_area_claims | CRMBuilder Delivery | access/repositories/planning_claims.py:claim_area | A single-threaded-by-area planning claim within a frozen release. | verified | none |
| ResourceLock | resource_locks | CRMBuilder Delivery | access/locks.py:acquire | A named-resource check-out lock for sub-agent fan-out. | verified | none |
| Release | releases | CRMBuilder Delivery | api/routers/releases.py via access/repositories/releases.py:_new_row | The release pipeline keystone: a container of release-scoped projects, in-scope requirements and planning items whose status is its pipeline stage. It references no instance, deploy run or publish. | verified | Shared Core |
| ReleaseChangeSet | release_change_sets | CRMBuilder Delivery | access/release_orchestration.py via access/repositories/release_change_sets.py:persist_change_set | The stored merged result of a release's reconciliation stage. | verified | none |
| ReleaseSignoff | release_signoffs | CRMBuilder Delivery | access/repositories/release_signoffs.py:create_signoff | A human sign-off gating a release's front-half transitions. | verified | none |
| ReleaseDemand | release_demands | CRMBuilder Delivery | scheduler/release_scheduler.py via access/repositories/release_demands.py:add_demands | The structured requirement-to-design deltas a reconciliation agent authors for a release. | verified | none |
| ReleaseRunRow | release_runs | CRMBuilder Delivery | access/repositories/release_runs.py:record | Born-terminal record of one release run's outcome. | verified | none |
| ArtifactVersion | artifact_versions | CRMBuilder Delivery | access/planning.py via access/repositories/artifact_versions.py:snapshot | A complete snapshot of one design artifact at one version, tied to the release that introduced it; written by the release pipeline's planning step. | verified | Solution Design |
| ReconciliationConflict | reconciliation_conflicts | CRMBuilder Delivery | access/repositories/reconciliation.py:_upsert_artifact_conflicts | A conflict found when the release reconciliation engine runs a frozen release's demanded deltas against artifact versions. Not the CRM instance reconcile. | verified | none |
| Finding | findings | CRMBuilder Delivery | access/repositories/findings.py:_new_row | A cross-area coherence problem found when a planning item's area specifications are checked against each other at the end of the release pipeline's design stage. | verified | Shared Core |
| AgentProfileRow | agent_profiles | CRMBuilder Delivery | access/repositories/agent_profiles.py:_new_row | The skill-and-rule definition for one agent role in the registry. | verified | Shared Core (session opening contract) |
| AgentProfileBindingRow | agent_profile_bindings | CRMBuilder Delivery | access/repositories/agent_profile_bindings.py:create | Binds a profile to skills and rules, system baseline or engagement overlay. | verified | Shared Core |
| SkillRow | skills | CRMBuilder Delivery | access/repositories/skills.py:_new_row | A reusable agent capability in the registry. | verified | none |
| LearningRow | learnings | CRMBuilder Delivery | access/repositories/learnings.py:_new_row | An evidence-tagged observation written by area experts; the registry's living memory. | verified | none |
| CostEvent | cost_events | CRMBuilder Delivery | access/repositories/cost_events.py:record | One model call's cost. | verified | none |
| BudgetApproval | budget_approvals | CRMBuilder Delivery | access/budget_gate.py:record_decision | An operator's pre-launch budget decision for an autonomous run. | verified | none |
| PipelineEvent | pipeline_events | CRMBuilder Delivery | access/repositories/pipeline_events.py:record | One pipeline step or agent invocation, for progress display. | verified | none |

### Shared Core

| Class | Table name | Owning segment | Creating operation | Evidence | Confidence | Readers |
|---|---|---|---|---|---|---|
| Session | sessions | Shared Core | access/repositories/sessions.py:_new_row | One unit of communication in any medium; the governance container every kind of work opens. | verified | all segments |
| Conversation | conversations | Shared Core | access/repositories/conversations.py:_new_row | A topical sub-unit of a session; the provenance root of every requirement. | verified | Discovery and Requirements |
| Decision | decisions | Shared Core | access/repositories/decisions.py:_new_decision_row | A recorded decision; the only path by which a requirement is confirmed. | verified | all segments |
| PlanningItem | planning_items | Shared Core | access/repositories/planning_items.py:_new_planning_item_row | The unit of governed work that implements a requirement. | verified | CRMBuilder Delivery |
| Project | projects | Shared Core | access/repositories/projects.py:_new_row | The first governance entity type, the container of planning items; the delivery pipeline reads it as its backlog but does not create it. | verified | CRMBuilder Delivery |
| Risk | risks | Shared Core | access/repositories/risks.py:_new_risk_row | A risk record from the original governance set; no docstring states its scope. | approved | Discovery and Requirements |
| Status | status | Shared Core | access/repositories/status.py:replace | The engagement's versioned status document, generated from its records. | approved | all segments |
| WorkTicket | work_tickets | Shared Core | access/repositories/work_tickets.py:_new_row | A single-use seed document a conversation consumes at kickoff. | approved | CRMBuilder Delivery |
| CloseOutPayload | close_out_payloads | Shared Core | access/repositories/close_out_payloads.py:_new_row | The close-out record a conversation produces. | verified | none |
| DepositEvent | deposit_events | Shared Core | access/repositories/deposit_events.py:create_deposit_event | The born-terminal record that a close-out was applied. | verified | none |
| Commit | commits | Shared Core | access/repositories/commits.py:_new_row | A documentary record of a code commit produced by a conversation. | verified | CRMBuilder Delivery |
| ReferenceBook | reference_books | Shared Core | api/routers/reference_books.py via access/repositories/reference_books.py:_new_row | The third governance entity type, a documentary reference with a versioned sibling. | verified | none |
| ReferenceBookVersion | reference_book_versions | Shared Core | access/repositories/reference_books.py:create_reference_book_version | One version of a reference book. | verified | none |
| GovernanceRuleRow | governance_rules | Shared Core | access/repositories/governance_rules.py:_new_row | A binding operating rule, system default or engagement override. | verified | all segments |
| RuleEnforcementOverrideRow | rule_enforcement_overrides | Shared Core | access/repositories/governance_rules.py:record_enforcement_override | A recorded wave-through of an enforced rule. | verified | none |
| PreferenceRow | preferences | Shared Core | access/repositories/preferences.py:_new_row | An advisory working-style preference. | verified | all segments |
| LessonRow | lessons | Shared Core | access/repositories/lessons.py:_new_row | One operational lesson. | verified | all segments |
| ReferencePointerRow | reference_pointers | Shared Core | access/repositories/reference_pointers.py:_new_row | One external addressable target: server, dashboard, document, credential location. | verified | all segments |
| TermRow | terms | Shared Core | access/repositories/terms.py:_new_row | One glossary definition. | verified | all segments |
| Topic | topics | Shared Core | access/repositories/topics.py:_new_topic_row | A filing concept created by Discovery (for requirements) and by governance (for its own corpus); cross-segment under the DEC-1086 addendum. | verified | Shared Core |

### Shared core plumbing

| Class | Table name | Owning segment | Creating operation | Evidence | Confidence | Readers |
|---|---|---|---|---|---|---|
| Reference | refs | Shared core plumbing | access/repositories/references.py:create | The universal cross-record reference graph; creating an edge can flip the state of either end. | verified | all segments |
| IdentifierReservation | identifier_reservations | Shared core plumbing | access/repositories/identifier_reservations.py:reserve | A reserved block of prefixed identifiers so concurrent writers never race. | verified | all segments |
| ChangeLog | change_log | Shared core plumbing | access/change_log.py:emit | One row per mutating repository call, for every record type. | verified | all segments |
| SecretValue | secret_values | Shared core plumbing | secrets.py:_store_put | An encrypted secret resolved through an opaque reference; never held on the owning row. | verified | Operate, Client Management |

## Placement notes

**The release family: Release, ReleaseChangeSet, ReleaseSignoff, ReleaseDemand, ReleaseRunRow.** These are releases of CRMBuilder's own delivery pipeline, not releases of a client's CRM to production. The release repository describes the release as a container of release-scoped projects, in-scope requirements and planning items, whose status is its pipeline stage, gated by freeze and planned-completely checks over those governance records. The repository never mentions an instance, a deploy run or a publish run. The sign-off, demand, change-set and run records are the stages and outputs of that same pipeline. All five are CRMBuilder Delivery. A client release to production is a deploy run or a publish run, which belong to Operate and Build respectively.

**ArtifactVersion.** A snapshot of one design artifact at one version, tied to the release that introduced it. The writer is the release pipeline's planning step. By the creating-operation rule it is CRMBuilder Delivery, and Solution Design is its reader.

**ReconciliationConflict versus ReconcileTransaction.** Two different reconciliations share a word. The reconciliation conflict is produced when the release pipeline runs a frozen release's demanded deltas against artifact versions; it is CRMBuilder Delivery. The reconcile transaction is the append-only trail of a reconcile action against a live CRM instance; it is Build.

**Finding.** Recorded when a planning item's area specifications are checked against each other at the end of the release pipeline's design stage. The design here is the pipeline's design phase, not the client's solution design. It is CRMBuilder Delivery. The rough sort had it under Build.

**ReferenceBook, ReferenceBookVersion, ReferenceEntry.** The reference book is the third governance entity type, a documentary record with versions; it is Shared Core. The reference entry is a different thing: cross-engagement client-industry knowledge for the discovery phase, seeded and extended for the consultant. It is Discovery and Requirements.

**EngagementArea, AreaSpec, AreaReopen, PlanningAreaClaim.** All four belong to the two-tier area model of the agent delivery organisation: the engagement area is the user-defined work-area label that work tasks carry, the area specification is what an area architect authors for a release, and the reopen and claim records are the release pipeline's area mechanics. All four are CRMBuilder Delivery. The engagement area has no link to a client business domain.

**Project.** The first governance entity type and the container of planning items. The delivery pipeline's project-manager substrate reads a project's backlog but does not create projects. Shared Core owns it; CRMBuilder Delivery reads it.

**TestSpec.** Authored against the design through the test-specification endpoints; the same repository offers a record_run helper that Build uses to record an execution. Solution Design creates it and owns it. Build records runs against it, so any move must keep that write path.

**Participant.** The real engagement person or role that a persona is backed by. It is created by its own repository and is the people half of a client engagement. It is Client Management, as DEC-1077 stated.

**CloseOutPayload, DepositEvent.** The close-out a conversation produces and the born-terminal record that it was applied. Both are governance bookkeeping and are Shared Core.

**MigrationMapping and the SourceMapping, FieldMapping, AssociationMapping, ValueMapping family.** These are two families. The source-mapping family records a human's resolution of a mapping candidate that an audit surfaced: how a discovered source entity, field, relationship or value relates to the design. The creating operations are the candidate-resolve dialog on the reconcile screens and the mapping endpoints. By the creating-operation rule they are Build. The counter-argument is that the kind of work they serve, describing a system the client already uses, belongs to the Requirements Capture domain, which would make them Discovery and Requirements. They are placed in Build and listed as open. The migration mapping is different: it states a data-migration obligation from a source to target fields with transform rules, a design-time statement a compiler consumes. It is placed in Solution Design and listed as open.

**SystemSetting and SystemSettingValue.** The setting is a design construct and is Solution Design. The value is what one instance is declared to hold, set through the settings endpoints and compared by the audit; it is placed in Build and listed as open because Operate, which owns the instance, is the alternative.

**Topic, Risk, Status, WorkTicket.** Four records from the earliest governance set with thin or no statements of purpose. Topics gate requirement approval and organise review, so they are placed with Discovery and Requirements, but they also organise the governance corpus. Risks, the status document and work tickets are placed with Shared Core. All four are listed as open.

**Service, SourceMappingJoin, FieldMappingTranslation.** Three tables have a model but no creating operation anywhere in the code. They are placed with their parents (the service with the design records, the join and translation with the mapping family) and listed as open. Each is a candidate for removal in the package move.

## Changes from the rough sort

The rough sort recorded on DEC-1079 had Solution Design 40, CRMBuilder Delivery 22, Shared Core 15, Discovery and Requirements 13, Build 7, Operate 5, Client Management 5, shared core 4. The checked mapping differs as follows.

- Finding moved from Build to CRMBuilder Delivery.
- ReconciliationConflict moved from Build to CRMBuilder Delivery; ReconcileTransaction stays in Build.
- Conversation moved from Discovery and Requirements to Shared Core: it is the governance sub-unit of a session, created by the governance repositories.
- Risk and Status moved from Discovery and Requirements to Shared Core.
- Charter stays in Discovery and Requirements as the Project Definition deliverable.
- ReferenceEntry moved from Shared Core to Discovery and Requirements.
- The nine mapping-family records (source, target, join, field, translation, association, value mappings and the migration mapping) moved from Solution Design: eight to Build, the migration mapping stays in Solution Design.
- InstanceMembership moved from Operate to Build: the audit and reconcile apply write it.
- ManualConfig, SystemSettingValue and ConformanceOverride are placed in Build.
- EngagementArea moved from Discovery and Requirements to CRMBuilder Delivery.

## Follow-on

Solution Design holds 31 of 111 record types. That segment will need its own internal division by design area before its lanes can run in parallel. A first suggested split:

- Data model: entity, field, field option, association, engine override, system setting, service.
- Access and security: role, team, field permission rule, field visibility rule.
- Views and layouts: view, layout, filtered tab.
- Behaviour: rule, automation, dedup rule, message template.
- Catalogue: the ten catalogue tables.
- Analysis and verification: CRM candidate, test specification, migration mapping.

The source-mapping family, if it stays in Build, is a second candidate for a sub-package of its own.

## Open placements

None. Every placement that was open in revision 0.1 was settled by the product owner on 09-14-26, one segment at a time. The three removal candidates were removed by PI-509 (REQ-601) on 09-15-26: their tables are dropped by branch revisions solution_design_0002 and build_0002, the reference type service and its two kinds are retired by shared_core_0002, and their rows stay listed below as history.

| Class | Settled placement | Ruling |
|---|---|---|
| Service | removal candidate | No creating operation exists; not assigned an owner. A later requirement may reintroduce it with an owner. |
| MigrationMapping | Solution Design | A design-time statement of intent, not the product of a run. |
| ManualConfig, SystemSettingValue, ConformanceOverride | Build | Created by Build operations; Operate reads them. |
| SourceMapping, SourceMappingTarget, FieldMapping, AssociationMapping, ValueMapping | Build | Created on the reconcile screens. The audit engine's dual use (baselining an existing system is discovery work; verifying a publish is build work) is a seam for the lane plan, not for this mapping. |
| SourceMappingJoin, FieldMappingTranslation | removal candidates | No creating operation exists. |
| Risk, Status, WorkTicket | Shared Core | More than one segment creates them (the DEC-1086 addendum). |
| Topic | Shared Core | Settled in revision 0.2 under the DEC-1086 addendum. |

## Appendix: non-record classes in the models module

| Class | What it is |
|---|---|
| _IdentifierFormatCheck | Constraint helper for prefixed identifiers |
| _LowerHexCheck | Constraint helper for hexadecimal columns |
| _NonEmptyJsonArrayCheck | Constraint helper for JSON array columns |
| _BooleanDomainCheck | Constraint helper for boolean columns |
| Base | The declarative base every table class extends |
| EngagementScopedPKMixin | The engagement-scope primary-key mixin; shared core plumbing |

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 0.1 | 09-14-26 01:17 | Claude (Claude Code, PI-504 lane) | First draft: 111 record types mapped from their creating operations; 16 placements left open for the product owner. |
| 0.2 | 09-14-26 17:08 | Claude (Claude Code, SES-414) | Ownership addendum DEC-1086: the group Governance Core is renamed Shared Core; Topic moves from Discovery and Requirements to the Shared Core and is no longer open; counts updated. Client Management approved by the product owner. |
| 1.0 | 09-14-26 17:33 | Claude (Claude Code, SES-414) | Approved by the product owner segment by segment: Discovery and Requirements, Solution Design, Build, Operate, CRMBuilder Delivery, Shared Core. All open placements settled; Service, SourceMappingJoin and FieldMappingTranslation marked removal candidates. Status set to Approved. |
| 1.1 | 09-15-26 00:39 | Claude (Claude Code, PI-509 lane) | The three removal candidates are removed (PI-509 / REQ-601): services, source_mapping_joins and field_mapping_translations dropped on their owners' branches; the service reference type and kinds retired on the shared_core branch. Counts 108; Solution Design 30, Build 14. |
