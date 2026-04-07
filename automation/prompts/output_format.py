"""Structured output format specification for CRM Builder Automation prompts.

Implements L2 PRD Section 10.5: defines the common JSON envelope (10.5.1)
and type-specific payload specifications (10.5.2) that tell the AI what
JSON structure to produce at the end of each session.
"""

# Work item types that produce prompts (9 of 12).
PROMPTABLE_ITEM_TYPES = frozenset({
    "master_prd",
    "business_object_discovery",
    "entity_prd",
    "domain_overview",
    "process_definition",
    "domain_reconciliation",
    "yaml_generation",
    "crm_selection",
    "crm_deployment",
})

# Work item types that do NOT produce prompts.
NON_PROMPTABLE_ITEM_TYPES = frozenset({
    "stakeholder_review",
    "crm_configuration",
    "verification",
})

COMMON_ENVELOPE = """\
{
  "output_version": "1.0",
  "work_item_type": "<work_item_type>",
  "work_item_id": <work_item_id>,
  "session_type": "<initial|revision|clarification>",
  "payload": { <type-specific payload — see below> },
  "decisions": [
    {
      "identifier": "<DEC-NNN>",
      "title": "<decision title>",
      "description": "<decision description>",
      "scope": {
        "domain_id": <int or null>,
        "entity_id": <int or null>,
        "process_id": <int or null>,
        "field_id": <int or null>,
        "requirement_id": <int or null>,
        "business_object_id": <int or null>
      }
    }
  ],
  "open_issues": [
    {
      "identifier": "<OI-NNN>",
      "title": "<issue title>",
      "description": "<issue description>",
      "priority": "<high|medium|low>",
      "scope": {
        "domain_id": <int or null>,
        "entity_id": <int or null>,
        "process_id": <int or null>,
        "field_id": <int or null>,
        "requirement_id": <int or null>,
        "business_object_id": <int or null>
      }
    }
  ]
}"""

# Type-specific payload descriptions per Section 10.5.2.
TYPE_PAYLOAD_SPECS: dict[str, str] = {
    "master_prd": """\
The payload object must contain:
- organization_overview: string — narrative prose describing the organization's mission, operating context, and CRM rationale.
- personas: array of objects, each with: name, description, responsibilities, crm_capabilities, identifier.
- domains: array of objects, each with: name, code, description, sort_order, sub_domains (array, optional).
- processes: array of objects grouped by domain, each with: name, code, description, sort_order, tier, business_value, key_capabilities, domain_code.
- cross_domain_services: array of objects, each with: name, description, capabilities, consuming_domains, owned_entities.
- system_scope: object with: in_scope (array of strings), out_of_scope (array of strings), integrations (array of strings).""",

    "business_object_discovery": """\
The payload object must contain:
- business_objects: array of objects, each with: name, description, source_domains, source_processes, classification (one of: entity, process, persona, field_value, lifecycle_state, relationship). For entity-classified objects also include: entity_name, entity_type, is_native, discriminator_field, discriminator_values.
- entity_participation: array of objects, each with: entity_name, primary_domain, additional_domains, participating_processes.
- dependency_order: array of entity names in recommended interview order.""",

    "entity_prd": """\
The payload object must contain:
- entity_metadata: object with: entity_type, is_native, contributing_domains, discriminator_details.
- native_fields: array of objects, each with: field_name, prd_name, field_type, referencing_processes.
- custom_fields: array of objects, each with: field_name, label, field_type, is_required, default_value, description, domain_attribution, visibility_rules, implementation_notes, and any type-specific properties (max_length, options, etc.).
- relationships: array of objects, each with: name, link_type, entity_foreign, link, link_foreign, label, label_foreign, domain_attribution.
- dynamic_logic: array of objects grouped by discriminator value, each with: condition, affected_fields, behavior.
- layout_guidance: object describing recommended panel organization.
- implementation_notes: array of strings.""",

    "domain_overview": """\
The payload object must contain:
- domain_purpose: string — expanded business context narrative.
- personas: array of objects, each with: identifier, domain_specific_role.
- business_process_inventory: array of objects with: process_name, process_code, dependency_order, description, lifecycle_narrative.
- data_reference: array of objects, each with: entity_identifier, referenced_fields, usage_notes.
- sub_domain_structure (optional, for parent domains): object with: rationale, cross_sub_domain_relationships, oversight_requirements.""",

    "process_definition": """\
The payload object must contain:
- process_purpose: string.
- triggers: object with: preconditions, required_data, initiation_mechanism, initiating_persona.
- personas: array of objects, each with: identifier, role.
- workflow: array of ordered step objects, each with: step_name, step_type (action|decision|system|notification), description, performer_persona, decision_points, status_transitions.
- completion: object with: end_states, handoffs.
- system_requirements: array of objects, each with: identifier, description, priority.
- process_data: array of objects grouped by entity, each with: entity_name, field_references.
- data_collected: array of objects grouped by entity, each with: entity_name, new_fields (array of field definitions).
- updates_to_prior_documents: array of objects, each with: document_type, entity_or_process, change_description.
- interview_transcript: string.""",

    "domain_reconciliation": """\
The payload object must contain:
- domain_overview_narrative: string.
- personas: array of objects, each with: identifier, consolidated_role.
- conflict_resolutions: array of objects, each with: affected_items, resolution_description.
- consolidated_data_reference: array of objects grouped by entity, each with: entity_name, deduplicated_fields.
- cross_process_gaps: array of strings describing identified gaps.
- sub_domain_reconciliation (optional, for parent domains): object with: consistency_resolutions, shared_entity_usage.""",

    "yaml_generation": """\
The payload object must contain:
- entity_configurations: array of objects with implementation-specific entity detail.
- relationship_configurations: array of relationship configuration objects.
- layout_definitions: array of objects, one per entity, with panel/row/tab layout detail.
- resolved_exceptions: array of objects, each with: description, resolution.
- unresolved_exceptions: array of objects, each with: description, impact.""",

    "crm_selection": """\
The payload object must contain:
- recommended_platforms: array of objects, each with: name, summary, strengths, tradeoffs, cost_considerations.
- requirements_coverage: array of objects, one per platform, each with: platform_name, coverage_assessment.
- platform_risks: array of objects, each with: platform_name, risk_description, severity, mitigation.""",

    "crm_deployment": """\
The payload object must contain:
- deployment_plan: object with: provisioning_steps (array), server_requirements.
- infrastructure_decisions: array of objects, each with: decision, rationale.
- platform_specific_notes: array of strings.
- open_items: array of strings.""",
}


def get_output_spec(
    item_type: str,
    work_item_id: int,
    session_type: str = "initial",
) -> str:
    """Return the Structured Output Specification text for a prompt.

    This text goes into Section 6 of the generated prompt. It tells the AI
    what JSON structure to produce at the end of the session.

    :param item_type: The work item's item_type.
    :param work_item_id: The WorkItem.id (for the envelope example).
    :param session_type: "initial", "revision", or "clarification".
    :returns: The specification text as a string.
    :raises ValueError: If item_type is not promptable.
    """
    if item_type not in PROMPTABLE_ITEM_TYPES:
        raise ValueError(
            f"Item type '{item_type}' does not produce prompts"
        )

    envelope = COMMON_ENVELOPE.replace("<work_item_type>", item_type)
    envelope = envelope.replace("<work_item_id>", str(work_item_id))

    payload_spec = TYPE_PAYLOAD_SPECS[item_type]

    clarification_note = ""
    if session_type == "clarification":
        clarification_note = (
            "\n\nNote: This is a clarification session. Structured output is "
            "optional — produce it only if the clarification reveals an error "
            "or needed correction. If no correction is needed, you may omit "
            "the JSON block entirely."
        )

    return (
        "# Structured Output Specification\n\n"
        "At the end of this session, produce a single JSON block enclosed "
        "in a ```json code fence. The JSON must conform to this structure:\n\n"
        f"```json\n{envelope}\n```\n\n"
        "## Payload Specification\n\n"
        f"{payload_spec}"
        f"{clarification_note}"
    )


def is_promptable(item_type: str) -> bool:
    """Return True if this item_type produces a prompt."""
    return item_type in PROMPTABLE_ITEM_TYPES
