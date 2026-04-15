"""Generate a Verification Spec from YAML program files."""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from espo_impl.core.config_loader import ConfigLoader
from tools.docgen.builders.verification_spec_builder import (
    build_external_dependencies_section,
)

logger = logging.getLogger(__name__)


def load_programs(programs_dir: Path) -> list:
    """Load all YAML program files from a directory.

    :param programs_dir: Directory containing YAML program files.
    :returns: List of ProgramFile objects.
    """
    loader = ConfigLoader()
    programs = []
    yaml_files = sorted(programs_dir.glob("*.yaml")) + sorted(
        programs_dir.glob("*.yml")
    )
    for path in yaml_files:
        try:
            program = loader.load_program(path)
            programs.append(program)
            logger.info("Loaded: %s", path.name)
        except Exception:
            logger.exception("Failed to load %s", path.name)
    return programs


def build_spec(programs_dir: Path) -> str:
    """Build the complete verification spec document.

    :param programs_dir: Directory containing YAML program files.
    :returns: Markdown content for the verification spec.
    """
    programs = load_programs(programs_dir)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        "# Verification Spec\n",
        f"Generated: {timestamp}\n",
    ]

    # Section: External Integration Dependencies
    lines.append(build_external_dependencies_section(programs))

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate Verification Spec from YAML program files"
    )
    parser.add_argument(
        "--programs",
        required=True,
        help="Directory containing YAML program files",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: {programs}/../reports/verification_spec.md)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    args = parse_args(argv)
    programs_dir = Path(args.programs)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = programs_dir.parent / "reports" / "verification_spec.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = build_spec(programs_dir)
    output_path.write_text(content, encoding="utf-8")
    print(f"Generated: {output_path}")


if __name__ == "__main__":
    main()
