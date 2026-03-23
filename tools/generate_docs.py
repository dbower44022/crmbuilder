"""Generate CBM CRM Reference documentation from YAML program files."""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.docgen.builders.appendix_builder import build_appendix_a, build_appendix_b
from tools.docgen.builders.entity_builder import build_entity_sections
from tools.docgen.builders.field_builder import build_field_sections
from tools.docgen.builders.layout_builder import build_layout_sections
from tools.docgen.builders.placeholder_builder import build_placeholder_sections
from tools.docgen.builders.view_builder import build_view_sections
from tools.docgen.models import DocDocument, DocParagraph, DocSection
from tools.docgen.renderers import docx_renderer, md_renderer
from tools.docgen.yaml_loader import get_version, load_programs, ordered_entities

logger = logging.getLogger(__name__)

INTRO_TEXT = (
    "This document is the authoritative implementation reference for the "
    "Cleveland Business Mentors CRM system built on EspoCRM. It defines "
    "every entity, field, layout, and configuration item required to support "
    "the requirements stated in the CBM PRD documents.\n\n"
    "This document is generated automatically from the YAML program files "
    "used by the EspoCRM Implementation Tool. To update this document, "
    "update the YAML files and regenerate.\n\n"
    "Sections marked 'Planned — Not Yet Implemented' describe future "
    "capability not yet supported by the deployment tool."
)


def build_document(
    programs_dir: Path,
    title: str,
    version: str | None = None,
) -> DocDocument:
    """Build the complete document from YAML program files.

    :param programs_dir: Directory containing YAML program files.
    :param title: Document title.
    :param version: Version override (or None to read from YAML).
    :returns: Complete DocDocument.
    """
    entities_dict = load_programs(programs_dir)
    entities = ordered_entities(entities_dict)
    doc_version = version or get_version(programs_dir)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    total_fields = sum(
        len(data.get("fields", []))
        for _, data in entities
    )
    logger.info("Loaded %d entities, %d fields", len(entities), total_fields)

    doc = DocDocument(
        title=title,
        subtitle="CRM Implementation Reference",
        version=doc_version,
        timestamp=timestamp,
    )

    # Section 1 — Introduction
    intro = DocSection(title="Introduction", level=1)
    intro.content.append(DocParagraph(text=INTRO_TEXT))
    doc.sections.append(intro)

    # Section 2 — Entities
    doc.sections.append(build_entity_sections(entities))

    # Section 3 — Fields
    doc.sections.append(build_field_sections(entities))

    # Section 4 — Layouts
    doc.sections.append(build_layout_sections(entities))

    # Section 5 — Views
    doc.sections.append(build_view_sections(entities))

    # Sections 6, 7, 8 — Placeholders
    doc.sections.extend(build_placeholder_sections())

    # Appendix A — Enum Reference
    doc.sections.append(build_appendix_a(entities))

    # Appendix B — Deployment Status
    doc.sections.append(build_appendix_b(entities))

    return doc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate CBM CRM Reference documentation from YAML"
    )
    parser.add_argument(
        "--programs",
        default="data/programs/",
        help="Directory containing YAML program files",
    )
    parser.add_argument(
        "--output",
        default="PRDs/Implementation Docs/",
        help="Output directory",
    )
    parser.add_argument(
        "--format",
        choices=["docx", "md", "both"],
        default="both",
        help="Output format",
    )
    parser.add_argument(
        "--title",
        default="CBM CRM Implementation Reference",
        help="Document title",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Override version string",
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
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = build_document(programs_dir, args.title, args.version)

    if args.format in ("md", "both"):
        md_path = output_dir / "CBM-CRM-Reference.md"
        md_path.write_text(md_renderer.render(doc), encoding="utf-8")
        print(f"Generated: {md_path}")

    if args.format in ("docx", "both"):
        docx_path = output_dir / "CBM-CRM-Reference.docx"
        docx_renderer.render(doc, docx_path)
        print(f"Generated: {docx_path}")


if __name__ == "__main__":
    main()
