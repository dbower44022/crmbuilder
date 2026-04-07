"""PromptGenerator — public API for CRM Builder Automation prompt generation.

Wraps all prompt modules into a single class that the UI (Step 15) and
other components will call. Produces a complete prompt string and records
an AISession row.
"""

import sqlite3

from automation.db.connection import transaction
from automation.prompts.context import assemble_context
from automation.prompts.context_size import reduce_context
from automation.prompts.decisions_issues import get_decisions, get_open_issues
from automation.prompts.guide_selection import get_guide_content
from automation.prompts.output_format import PROMPTABLE_ITEM_TYPES, get_output_spec
from automation.prompts.session_types import (
    build_session_header,
    get_prior_output_for_revision,
    get_session_instructions_preamble,
    validate_session_params,
)
from automation.prompts.structure import assemble_prompt
from automation.workflow.engine import WorkflowEngine
from automation.workflow.phases import get_phase_name


def _get_item_description(conn: sqlite3.Connection, work_item: dict) -> str:
    """Build a human-readable description for a work item.

    E.g. "Contact Entity PRD" or "Client Intake (MN-INTAKE) Process Definition".
    """
    item_type = work_item["item_type"]
    parts = []

    if work_item.get("entity_id"):
        row = conn.execute(
            "SELECT name FROM Entity WHERE id = ?", (work_item["entity_id"],)
        ).fetchone()
        if row:
            parts.append(row[0])

    if work_item.get("process_id"):
        row = conn.execute(
            "SELECT name, code FROM Process WHERE id = ?", (work_item["process_id"],)
        ).fetchone()
        if row:
            parts.append(f"{row[0]} ({row[1]})")

    if work_item.get("domain_id") and not parts:
        row = conn.execute(
            "SELECT name FROM Domain WHERE id = ?", (work_item["domain_id"],)
        ).fetchone()
        if row:
            parts.append(row[0])

    # Map item_type to readable label
    type_labels = {
        "master_prd": "Master PRD",
        "business_object_discovery": "Business Object Discovery",
        "entity_prd": "Entity PRD",
        "domain_overview": "Domain Overview",
        "process_definition": "Process Definition",
        "domain_reconciliation": "Domain Reconciliation",
        "stakeholder_review": "Stakeholder Review",
        "yaml_generation": "YAML Generation",
        "crm_selection": "CRM Selection",
        "crm_deployment": "CRM Deployment",
        "crm_configuration": "CRM Configuration",
        "verification": "Verification",
    }
    label = type_labels.get(item_type, item_type)

    if parts:
        return f"{' — '.join(parts)} {label}"
    return label


class PromptGenerator:
    """Public API for prompt generation.

    All methods operate on the connections provided at construction time.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        master_conn: sqlite3.Connection | None = None,
    ) -> None:
        """Initialize with database connections.

        :param conn: Open client database connection.
        :param master_conn: Optional master database connection, required
            for work item types that need Client data (master_prd,
            business_object_discovery, domain_overview, crm_selection,
            crm_deployment).
        """
        self._conn = conn
        self._master_conn = master_conn
        self._engine = WorkflowEngine(conn)

    def is_promptable(self, item_type: str) -> bool:
        """Return True if this item_type produces a prompt."""
        return item_type in PROMPTABLE_ITEM_TYPES

    def generate(
        self,
        work_item_id: int,
        session_type: str = "initial",
        revision_reason: str | None = None,
        clarification_topic: str | None = None,
    ) -> str:
        """Generate a complete prompt for the given work item.

        Returns the prompt as a single string. Also creates an AISession
        row recording the generated prompt and session metadata.

        :param work_item_id: The WorkItem.id.
        :param session_type: "initial", "revision", or "clarification".
        :param revision_reason: Required for revision sessions.
        :param clarification_topic: Required for clarification sessions.
        :returns: The complete prompt text.
        :raises ValueError: On validation failure (see docstring in prompt).
        """
        # Validate session params
        validate_session_params(session_type, revision_reason, clarification_topic)

        # Fetch work item
        row = self._conn.execute(
            "SELECT id, item_type, status, domain_id, entity_id, process_id "
            "FROM WorkItem WHERE id = ?",
            (work_item_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Work item {work_item_id} not found")

        work_item = {
            "id": row[0], "item_type": row[1], "status": row[2],
            "domain_id": row[3], "entity_id": row[4], "process_id": row[5],
        }

        # Validate status
        if work_item["status"] not in ("ready", "in_progress"):
            raise ValueError(
                f"Cannot generate prompt for work item {work_item_id}: "
                f"status is '{work_item['status']}', expected 'ready' or 'in_progress'"
            )

        # Validate promptable
        if not self.is_promptable(work_item["item_type"]):
            raise ValueError(
                f"Work item type '{work_item['item_type']}' does not require "
                "a prompt (stakeholder_review, crm_configuration, verification "
                "are handled outside the Prompt Generator)"
            )

        # Get phase info
        phase_number = self._engine.get_phase_for(work_item_id)
        phase_name = get_phase_name(phase_number)

        # Build item description
        item_desc = _get_item_description(self._conn, work_item)

        # Section 1: Session Header
        header = build_session_header(
            work_item["item_type"], item_desc, session_type,
            phase_number, phase_name,
            revision_reason=revision_reason,
            clarification_topic=clarification_topic,
        )

        # Section 2: Session Instructions
        preamble = get_session_instructions_preamble(session_type)
        if session_type == "clarification":
            # Clarification: minimal instructions, no full guide
            instructions = preamble or ""
        else:
            guide = get_guide_content(work_item["item_type"])
            if preamble:
                instructions = preamble + "\n\n" + guide
            else:
                instructions = guide

        # Section 3: Context
        context = assemble_context(
            self._conn, work_item_id, work_item["item_type"], self._master_conn,
        )

        # For revision/clarification: include prior structured output
        if session_type in ("revision", "clarification"):
            prior_output = get_prior_output_for_revision(self._conn, work_item_id)
            if prior_output:
                context["subsections"].append({
                    "label": "Prior Session Output",
                    "content": prior_output,
                    "priority": 2,
                })

        # Apply context size management
        p1_text = header + "\n" + instructions
        output_spec = get_output_spec(
            work_item["item_type"], work_item_id, session_type,
        )
        p1_text += "\n" + output_spec
        context, reduction_strategies = reduce_context(context, p1_text)

        # Section 4 & 5: Decisions and Issues
        decisions = get_decisions(
            self._conn, work_item["item_type"], work_item,
        )
        open_issues = get_open_issues(
            self._conn, work_item["item_type"], work_item,
        )

        # Assemble
        prompt = assemble_prompt(
            header, instructions, context, decisions, open_issues, output_spec,
        )

        # Add reduction notice if any strategies were applied
        if reduction_strategies:
            notice = "\n\n<!-- Context reduction applied: " + "; ".join(reduction_strategies) + " -->"
            prompt += notice

        # Record AISession
        with transaction(self._conn):
            self._conn.execute(
                "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
                "import_status, started_at) VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)",
                (work_item_id, session_type, prompt),
            )

        return prompt
