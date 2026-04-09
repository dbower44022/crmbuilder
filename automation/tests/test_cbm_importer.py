"""Tests for CBM importer parsers against fixture subset documents."""

from pathlib import Path

from automation.cbm_import.parser_logic import (
    extract_enum_values,
    extract_section_text,
    find_section_by_heading,
    parse_field_table,
    parse_header_table,
    parse_persona_list,
    parse_requirement_list,
)
from automation.cbm_import.reporter import ImportReport

FIXTURES = Path(__file__).parent / "fixtures" / "cbm_subset"


# ---------------------------------------------------------------------------
# parser_logic tests (pure Python, no docx)
# ---------------------------------------------------------------------------


class TestFindSectionByHeading:

    def test_finds_heading(self):
        paras = ["Intro", "2. Personas", "Some content"]
        assert find_section_by_heading(paras, r"personas") == 1

    def test_returns_none_when_missing(self):
        paras = ["Intro", "Content"]
        assert find_section_by_heading(paras, r"personas") is None

    def test_case_insensitive(self):
        paras = ["1. ORGANIZATION OVERVIEW"]
        assert find_section_by_heading(paras, r"organization\s+overview") == 0


class TestExtractSectionText:

    def test_extracts_until_next_heading(self):
        paras = ["1. Heading", "Content line 1", "Content line 2", "2. Next heading"]
        text = extract_section_text(paras, 0)
        assert "Content line 1" in text
        assert "Content line 2" in text
        assert "Next heading" not in text

    def test_extracts_to_end(self):
        paras = ["1. Heading", "Only content"]
        text = extract_section_text(paras, 0)
        assert text == "Only content"


class TestParseHeaderTable:

    def test_parses_key_value_pairs(self):
        rows = [
            ["Document Type", "Master PRD"],
            ["Version", "2.3"],
        ]
        result = parse_header_table(rows)
        assert result["Document Type"] == "Master PRD"
        assert result["Version"] == "2.3"


class TestParseFieldTable:

    def test_parses_fields(self):
        rows = [
            ["Field Name", "Type", "Required", "Values", "Default", "ID"],
            ["contactType", "multiEnum", "Yes", "Client | Mentor", "—", "DAT-001"],
            ["preferredName", "varchar", "No", "", "—", "DAT-002"],
        ]
        fields = parse_field_table(rows)
        assert len(fields) == 2
        assert fields[0]["field_name"] == "contactType"
        assert fields[0]["field_type"] == "multiEnum"
        assert fields[1]["field_name"] == "preferredName"

    def test_skips_empty_rows(self):
        rows = [
            ["Field Name", "Type"],
            ["", ""],
            ["email", "email"],
        ]
        fields = parse_field_table(rows)
        assert len(fields) == 1


class TestExtractEnumValues:

    def test_pipe_separated(self):
        values = extract_enum_values("Client | Mentor | Partner")
        assert values == ["Client", "Mentor", "Partner"]

    def test_comma_separated(self):
        values = extract_enum_values("Active, Inactive, On Hold")
        assert values == ["Active", "Inactive", "On Hold"]

    def test_dash_returns_empty(self):
        assert extract_enum_values("—") == []

    def test_empty_returns_empty(self):
        assert extract_enum_values("") == []


class TestParsePersonaList:

    def test_extracts_personas(self):
        paras = [
            "2. Personas",
            "MST-PER-001: System Administrator — Manages CRM",
            "MST-PER-002: Executive Member — Strategic oversight",
            "3. Next section",
        ]
        personas = parse_persona_list(paras, 0)
        assert len(personas) == 2
        assert personas[0]["code"] == "MST-PER-001"
        assert personas[0]["name"] == "System Administrator"


class TestParseRequirementList:

    def test_extracts_requirements(self):
        paras = [
            "6. System Requirements",
            "MN-INTAKE-REQ-001: Accept form submissions",
            "MN-INTAKE-REQ-002: Auto-create records",
            "7. Process Data",
        ]
        reqs = parse_requirement_list(paras, 0)
        assert len(reqs) == 2
        assert reqs[0]["identifier"] == "MN-INTAKE-REQ-001"


# ---------------------------------------------------------------------------
# Reporter tests
# ---------------------------------------------------------------------------


class TestImportReport:

    def test_record_counts(self):
        report = ImportReport()
        report.record_parsed("Entity", 3)
        report.record_imported("Entity", 2)
        assert report.total_parsed == 3
        assert report.total_imported == 2

    def test_skipped_records(self):
        report = ImportReport()
        report.record_skipped("test.docx", "Field", "email", "Duplicate")
        assert len(report.skipped) == 1
        assert report.skipped[0].reason == "Duplicate"

    def test_merge(self):
        r1 = ImportReport()
        r1.record_parsed("Entity", 2)
        r2 = ImportReport()
        r2.record_parsed("Entity", 3)
        r2.add_warning("test warning")
        r1.merge(r2)
        assert r1.parsed["Entity"] == 5
        assert len(r1.warnings) == 1

    def test_summary(self):
        report = ImportReport()
        report.record_parsed("Entity", 3)
        report.record_imported("Entity", 2)
        text = report.summary()
        assert "Parsed:   3 records" in text
        assert "Imported: 2 records" in text


# ---------------------------------------------------------------------------
# Parser tests against fixture documents
# ---------------------------------------------------------------------------


class TestMasterPrdParser:

    def test_parse_fixture(self):
        from automation.cbm_import.parsers.master_prd import parse
        data, report = parse(FIXTURES / "CBM-Master-PRD.docx")

        assert len(data["personas"]) >= 3
        codes = {p["code"] for p in data["personas"]}
        assert "MST-PER-001" in codes
        assert "MST-PER-003" in codes

        assert len(data["domains"]) >= 2
        domain_codes = {d["code"] for d in data["domains"]}
        assert "MN" in domain_codes
        assert "MR" in domain_codes

        assert len(data["processes"]) >= 2
        proc_codes = {p["code"] for p in data["processes"]}
        assert "MN-INTAKE" in proc_codes

        assert not report.errors


class TestEntityInventoryParser:

    def test_parse_fixture(self):
        from automation.cbm_import.parsers.entity_inventory import parse
        data, report = parse(FIXTURES / "CBM-Entity-Inventory.docx")

        assert len(data["business_objects"]) >= 2
        assert len(data["entities"]) >= 2

        entity_names = {e["name"] for e in data["entities"]}
        assert "Contact" in entity_names
        assert "Account" in entity_names

        assert not report.errors


class TestEntityPrdParser:

    def test_parse_contact_fixture(self):
        from automation.cbm_import.parsers.entity_prd import parse
        data, report = parse(FIXTURES / "entities" / "Contact-Entity-PRD.docx")

        assert data["entity"]["name"] == "Contact"
        assert data["entity"]["is_native"] is True

        assert len(data["fields"]) >= 3
        field_names = {f["name"] for f in data["fields"]}
        assert "contactType" in field_names
        assert "preferredName" in field_names

        # Check enum options extracted
        assert len(data["field_options"]) >= 3

        assert not report.errors


class TestProcessDocumentParser:

    def test_parse_intake_fixture(self):
        from automation.cbm_import.parsers.process_document import parse
        data, report = parse(FIXTURES / "MN" / "MN-INTAKE.docx")

        assert data["process"]["code"] == "MN-INTAKE"
        assert data["process"]["domain_code"] == "MN"
        assert "Client Intake" in data["process"]["name"]

        assert len(data["steps"]) >= 3
        assert len(data["requirements"]) >= 2

        req_ids = {r["identifier"] for r in data["requirements"]}
        assert "MN-INTAKE-REQ-001" in req_ids

        assert not report.errors


class TestDomainPrdParser:

    def test_parse_mentoring_fixture(self):
        from automation.cbm_import.parsers.domain_prd import parse
        data, report = parse(FIXTURES / "MN" / "CBM-Domain-PRD-Mentoring.docx")

        assert data["domain_code"] == "MN"
        assert len(data["domain_overview_text"]) > 50

        assert len(data["decisions"]) >= 2
        dec_ids = {d["identifier"] for d in data["decisions"]}
        assert "MN-DEC-001" in dec_ids

        assert not report.errors
