"""Interview guide selection for CRM Builder Automation prompts.

Implements L2 PRD Section 10.7: each prompt-capable work item type maps to
exactly one prompt-optimized interview guide file.

Guide files are stored at PRDs/process/interviews/prompt-optimized/.
When a guide file is not found, a placeholder is returned.
"""

from pathlib import Path

# Base directory for prompt-optimized interview guides.
_GUIDES_DIR = Path("PRDs/process/interviews/prompt-optimized")

# Mapping of item_type to guide filename per Section 10.7.
GUIDE_FILENAMES: dict[str, str] = {
    "master_prd": "prompt-master-prd.md",
    "business_object_discovery": "prompt-business-object-discovery.md",
    "entity_prd": "prompt-entity-prd.md",
    "domain_overview": "prompt-domain-overview.md",
    "process_definition": "prompt-process-definition.md",
    "domain_reconciliation": "prompt-domain-reconciliation.md",
    "yaml_generation": "prompt-yaml-generation.md",
    "crm_selection": "prompt-crm-selection.md",
    "crm_deployment": "prompt-crm-deployment.md",
}

_PLACEHOLDER = (
    "[Guide not yet authored for this work item type. "
    "The prompt-optimized interview guide has not been created. "
    "Proceed using general session instructions.]"
)


def get_guide_path(item_type: str, base_dir: Path | None = None) -> Path:
    """Return the filesystem path to the interview guide for this item_type.

    :param item_type: The work item's item_type.
    :param base_dir: Override the base directory (for testing).
    :returns: Path to the guide file.
    :raises ValueError: If item_type has no guide mapping.
    """
    filename = GUIDE_FILENAMES.get(item_type)
    if filename is None:
        raise ValueError(f"No interview guide mapping for item_type '{item_type}'")
    directory = base_dir if base_dir is not None else _GUIDES_DIR
    return directory / filename


def get_guide_content(item_type: str, base_dir: Path | None = None) -> str:
    """Read and return the interview guide content for this item_type.

    Returns a placeholder string if the guide file does not exist.

    :param item_type: The work item's item_type.
    :param base_dir: Override the base directory (for testing).
    :returns: The guide content or a placeholder.
    :raises ValueError: If item_type has no guide mapping.
    """
    path = get_guide_path(item_type, base_dir)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return _PLACEHOLDER


def is_guide_available(item_type: str, base_dir: Path | None = None) -> bool:
    """Check whether the interview guide file exists on disk.

    :param item_type: The work item's item_type.
    :param base_dir: Override the base directory (for testing).
    :returns: True if the file exists.
    """
    try:
        path = get_guide_path(item_type, base_dir)
        return path.exists()
    except ValueError:
        return False
