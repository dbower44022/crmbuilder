"""Import report generation for the CBM importer.

Tracks parsed records, imported records, skipped records, and warnings.
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class SkippedRecord:
    """A record that could not be imported."""

    source_file: str
    table_name: str
    identifier: str | None
    reason: str


@dataclasses.dataclass
class ImportReport:
    """Report of a CBM import operation."""

    parsed: dict[str, int] = dataclasses.field(default_factory=dict)
    imported: dict[str, int] = dataclasses.field(default_factory=dict)
    skipped: list[SkippedRecord] = dataclasses.field(default_factory=list)
    warnings: list[str] = dataclasses.field(default_factory=list)
    errors: list[str] = dataclasses.field(default_factory=list)

    def record_parsed(self, table_name: str, count: int = 1) -> None:
        """Record that records were parsed from a document."""
        self.parsed[table_name] = self.parsed.get(table_name, 0) + count

    def record_imported(self, table_name: str, count: int = 1) -> None:
        """Record that records were written to the database."""
        self.imported[table_name] = self.imported.get(table_name, 0) + count

    def record_skipped(
        self, source_file: str, table_name: str,
        identifier: str | None, reason: str,
    ) -> None:
        """Record that a record was skipped."""
        self.skipped.append(SkippedRecord(source_file, table_name, identifier, reason))

    def add_warning(self, message: str) -> None:
        """Add a non-fatal warning."""
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        """Add a fatal error that halted a sub-import."""
        self.errors.append(message)

    def merge(self, other: ImportReport) -> None:
        """Merge another report into this one."""
        for table, count in other.parsed.items():
            self.parsed[table] = self.parsed.get(table, 0) + count
        for table, count in other.imported.items():
            self.imported[table] = self.imported.get(table, 0) + count
        self.skipped.extend(other.skipped)
        self.warnings.extend(other.warnings)
        self.errors.extend(other.errors)

    @property
    def total_parsed(self) -> int:
        """Total number of parsed records across all tables."""
        return sum(self.parsed.values())

    @property
    def total_imported(self) -> int:
        """Total number of imported records across all tables."""
        return sum(self.imported.values())

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = ["=== CBM Import Report ==="]
        lines.append(f"Parsed:   {self.total_parsed} records")
        lines.append(f"Imported: {self.total_imported} records")
        lines.append(f"Skipped:  {len(self.skipped)} records")
        lines.append(f"Warnings: {len(self.warnings)}")
        lines.append(f"Errors:   {len(self.errors)}")

        if self.parsed:
            lines.append("\nParsed by table:")
            for table, count in sorted(self.parsed.items()):
                imported = self.imported.get(table, 0)
                lines.append(f"  {table}: {count} parsed, {imported} imported")

        if self.skipped:
            lines.append("\nSkipped records:")
            for s in self.skipped:
                lines.append(f"  [{s.table_name}] {s.identifier or '?'}: {s.reason} ({s.source_file})")

        if self.warnings:
            lines.append("\nWarnings:")
            for w in self.warnings:
                lines.append(f"  {w}")

        if self.errors:
            lines.append("\nErrors:")
            for e in self.errors:
                lines.append(f"  {e}")

        return "\n".join(lines)
