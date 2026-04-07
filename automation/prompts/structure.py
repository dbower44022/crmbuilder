"""Prompt assembly for CRM Builder Automation.

Implements L2 PRD Section 10.2: assembles the six-section prompt structure
from inputs provided by other modules and returns the complete prompt as
a single text string.

Section order:
1. Session Header
2. Session Instructions
3. Context
4. Locked Decisions
5. Open Issues
6. Structured Output Specification
"""

import json


def _format_context_section(context: dict) -> str:
    """Format the context dict into readable markdown."""
    lines = ["# Context"]
    for sub in context.get("subsections", []):
        label = sub.get("label", "")
        content = sub.get("content")
        lines.append("")
        lines.append(f"## {label}")
        lines.append("")
        if isinstance(content, str):
            lines.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if k == "id" or k.endswith("_id"):
                            continue
                        if isinstance(v, (list, dict)):
                            lines.append(f"- **{k}:** {json.dumps(v, default=str, indent=2)}")
                        elif v is not None:
                            lines.append(f"- **{k}:** {v}")
                    lines.append("")
                else:
                    lines.append(f"- {item}")
        elif isinstance(content, dict):
            for k, v in content.items():
                if isinstance(v, (list, dict)):
                    lines.append(f"**{k}:** {json.dumps(v, default=str, indent=2)}")
                elif v is not None:
                    lines.append(f"**{k}:** {v}")
        else:
            lines.append(str(content))
    return "\n".join(lines)


def _format_decisions(decisions: list[dict]) -> str:
    """Format locked decisions into markdown."""
    if not decisions:
        return "# Locked Decisions — do not reopen\n\nNo locked decisions in scope."
    lines = ["# Locked Decisions — do not reopen"]
    for d in decisions:
        lines.append("")
        identifier = d.get("identifier", "")
        title = d.get("title", "")
        description = d.get("description", "")
        lines.append(f"**{identifier}: {title}**")
        lines.append(f"{description}")
    return "\n".join(lines)


def _format_open_issues(issues: list[dict]) -> str:
    """Format open issues into markdown."""
    if not issues:
        return "# Open Issues — attempt to resolve or note impact\n\nNo open issues in scope."
    lines = ["# Open Issues — attempt to resolve or note impact"]
    for oi in issues:
        lines.append("")
        identifier = oi.get("identifier", "")
        title = oi.get("title", "")
        description = oi.get("description", "")
        priority = oi.get("priority", "")
        lines.append(f"**{identifier}: {title}** (Priority: {priority})")
        lines.append(f"{description}")
    return "\n".join(lines)


def assemble_prompt(
    header: str,
    instructions: str,
    context: dict,
    decisions: list[dict],
    open_issues: list[dict],
    output_spec: str,
) -> str:
    """Assemble the six sections into a complete prompt string.

    :param header: Session Header text (Section 1).
    :param instructions: Session Instructions text (Section 2).
    :param context: Context dict from context assembly (Section 3).
    :param decisions: List of Decision dicts (Section 4).
    :param open_issues: List of OpenIssue dicts (Section 5).
    :param output_spec: Structured Output Specification text (Section 6).
    :returns: The complete prompt as a single string.
    """
    sections = [
        header,
        "---",
        "# Session Instructions\n\n" + instructions,
        "---",
        _format_context_section(context),
        "---",
        _format_decisions(decisions),
        "---",
        _format_open_issues(open_issues),
        "---",
        output_spec,
    ]
    return "\n\n".join(sections)
