"""Assemble and save the Master PRD interview prompt.

Pure-logic module with no Qt dependencies.  The UI layer calls these
functions and handles clipboard / message-box interactions itself.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from automation.core.active_client_state import Client


def build_master_prd_prompt(client: Client, guide_path: Path) -> str:
    """Assemble the full prompt text: header + interview guide body.

    :param client: The selected Client.
    :param guide_path: Absolute path to interview-master-prd.md.
    :returns: Full prompt text ready to paste into Claude.ai.
    :raises FileNotFoundError: If guide_path does not exist.
    """
    guide_body = guide_path.read_text(encoding="utf-8")
    timestamp = datetime.now().strftime("%m-%d-%y %H:%M")
    header = (
        f"# Master PRD Interview — {client.name}\n\n"
        f"**Client:** {client.name}\n"
        f"**Code:** {client.code}\n"
        f"**Date:** {timestamp}\n\n"
        f"You are helping define the Master PRD for {client.name}. "
        f"Follow the interview guide below. Produce the Master PRD as "
        f"a Word document following CRM Builder document standards "
        f"(Arial, #1F3864 headings, two-column requirement tables, "
        f"alternating row shading #F2F7FB, body 11pt, US Letter, 1\" "
        f"margins). Do not mention specific product names "
        f"(EspoCRM, WordPress, etc.) in the Master PRD — product "
        f"names belong only in implementation documentation.\n\n"
        f"---\n\n"
    )
    return header + guide_body


def save_master_prd_prompt(
    prompt_text: str,
    project_folder: str,
    client_code: str,
) -> Path:
    """Write the prompt to {project_folder}/prompts/.

    Filename format: master-prd-prompt-{client_code}-{YYYYMMDD-HHMMSS}.md

    :param prompt_text: Full assembled prompt text.
    :param project_folder: Absolute path to client project folder.
    :param client_code: Client code, used in filename.
    :returns: The Path the file was written to.
    :raises OSError: If the directory cannot be created or file written.
    """
    folder = Path(project_folder) / "prompts"
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"master-prd-prompt-{client_code}-{timestamp}.md"
    file_path = folder / filename
    file_path.write_text(prompt_text, encoding="utf-8")
    return file_path
