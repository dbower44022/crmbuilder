"""Template rendering for CRM Builder Automation prompts.

Implements L2 PRD Section 10.8: reads template files, replaces placeholder
tokens with database-derived content, and filters session-type-conditional
blocks.

Templates are stored at PRDs/process/interviews/prompt-templates/template-{item_type}.md.
When a template file does not exist, a default template with section markers
is returned.
"""

import re
from pathlib import Path

_TEMPLATES_DIR = Path("PRDs/process/interviews/prompt-templates")

# Session-type block markers: <!-- IF session_type:initial --> ... <!-- ENDIF -->
_BLOCK_PATTERN = re.compile(
    r"<!-- IF session_type:(\w+) -->\n?(.*?)<!-- ENDIF -->",
    re.DOTALL,
)


def _default_template() -> str:
    """Return a minimal default template with section markers."""
    return (
        "{{SESSION_HEADER}}\n\n"
        "---\n\n"
        "{{SESSION_INSTRUCTIONS}}\n\n"
        "---\n\n"
        "# Context\n\n"
        "{{CONTEXT}}\n\n"
        "---\n\n"
        "{{DECISIONS}}\n\n"
        "---\n\n"
        "{{OPEN_ISSUES}}\n\n"
        "---\n\n"
        "{{OUTPUT_SPEC}}"
    )


def get_template_path(item_type: str, base_dir: Path | None = None) -> Path:
    """Return the filesystem path to the template for this item_type.

    :param item_type: The work item's item_type.
    :param base_dir: Override the base directory (for testing).
    :returns: Path to the template file.
    """
    directory = base_dir if base_dir is not None else _TEMPLATES_DIR
    return directory / f"template-{item_type}.md"


def load_template(item_type: str, base_dir: Path | None = None) -> tuple[str, bool]:
    """Load a template file, or return the default if not found.

    :param item_type: The work item's item_type.
    :param base_dir: Override the base directory (for testing).
    :returns: Tuple of (template_text, is_custom). is_custom is True if the
        template was loaded from a file, False if the default was used.
    """
    path = get_template_path(item_type, base_dir)
    if path.exists():
        return path.read_text(encoding="utf-8"), True
    return _default_template(), False


def filter_session_blocks(template: str, session_type: str) -> str:
    """Remove session-type-conditional blocks that don't match.

    Blocks are marked with:
        <!-- IF session_type:initial -->
        ... content ...
        <!-- ENDIF -->

    Blocks matching the current session_type have their markers stripped
    but content preserved. Non-matching blocks are removed entirely.
    """
    def replace_block(match: re.Match) -> str:
        block_type = match.group(1)
        content = match.group(2)
        if block_type == session_type:
            return content.strip("\n")
        return ""

    return _BLOCK_PATTERN.sub(replace_block, template)


def render_template(
    template: str,
    tokens: dict[str, str],
    session_type: str = "initial",
) -> str:
    """Render a template by replacing tokens and filtering session blocks.

    :param template: The template text (from load_template).
    :param tokens: Dict mapping placeholder names (without braces) to values.
    :param session_type: The session type for block filtering.
    :returns: The rendered template.
    """
    # Filter session-type blocks first
    result = filter_session_blocks(template, session_type)

    # Replace placeholder tokens: {{TOKEN_NAME}}
    for key, value in tokens.items():
        result = result.replace("{{" + key + "}}", value)

    return result
