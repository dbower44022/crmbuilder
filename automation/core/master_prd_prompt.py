"""Assemble and save the Master PRD interview prompt.

Pure-logic module with no Qt dependencies.  The UI layer calls these
functions and handles clipboard / message-box interactions itself.

Implements L2 PRD Section 10 for the ``master_prd`` work item type:
loads the prompt template and prompt-optimized interview guide,
substitutes placeholder tokens with database-derived context, and
returns the assembled prompt text that instructs the AI to produce
structured JSON output.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from automation.core.active_client_state import Client

# Paths relative to the repository root.
_TEMPLATE_REL = (
    "PRDs/process/interviews/prompt-templates/template-master_prd.md"
)
_GUIDE_REL = (
    "PRDs/process/interviews/prompt-optimized/prompt-master-prd.md"
)


def _repo_root() -> Path:
    """Return the repository root (three levels up from this file)."""
    return Path(__file__).resolve().parent.parent.parent


def build_master_prd_prompt(
    client: Client,
    work_item_id: int | None = None,
    session_type: str = "initial",
) -> str:
    """Assemble the full prompt text from the template and guide.

    :param client: The selected Client.
    :param work_item_id: WorkItem.id for the envelope spec (placeholder
        text if ``None``).
    :param session_type: Session type — ``"initial"``, ``"revision"``,
        or ``"clarification"``.
    :returns: Full prompt text ready to paste into Claude.ai.
    :raises FileNotFoundError: If the template or guide file is missing.
    """
    root = _repo_root()
    template_path = root / _TEMPLATE_REL
    guide_path = root / _GUIDE_REL

    template_body = template_path.read_text(encoding="utf-8")
    guide_body = guide_path.read_text(encoding="utf-8")

    timestamp = datetime.now().strftime("%m-%d-%y %H:%M")

    wid_str = str(work_item_id) if work_item_id is not None else "<work_item_id>"

    # Substitute the guide body into the template first (it may contain
    # its own {work_item_id} and {session_type} placeholders).
    guide_rendered = guide_body.replace(
        "{work_item_id}", wid_str,
    ).replace(
        "{session_type}", session_type,
    )

    prompt = template_body.replace(
        "{prompt_optimized_guide_body}", guide_rendered,
    ).replace(
        "{client_name}", client.name,
    ).replace(
        "{client_code}", client.code,
    ).replace(
        "{work_item_id}", wid_str,
    ).replace(
        "{session_type}", session_type,
    ).replace(
        "{generated_at}", timestamp,
    )

    return prompt


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
