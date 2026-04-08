"""Tests for automation.docgen.validation — data dictionary completeness."""

from automation.docgen import DocumentType
from automation.docgen.validation import validate


class TestValidation:

    def test_master_prd_missing_overview(self):
        data = {"organization_overview": None, "personas": [], "domains": []}
        warnings = validate(DocumentType.MASTER_PRD, data)
        fields = {w.field for w in warnings}
        assert "organization_overview" in fields
        assert "personas" in fields
        assert "domains" in fields

    def test_master_prd_complete(self):
        data = {
            "organization_overview": "Overview text",
            "personas": [{"name": "Admin"}],
            "domains": [{"name": "Test"}],
        }
        warnings = validate(DocumentType.MASTER_PRD, data)
        assert len(warnings) == 0

    def test_entity_prd_no_fields(self):
        data = {"entity": {"name": "Contact"}, "fields": []}
        warnings = validate(DocumentType.ENTITY_PRD, data)
        assert any(w.field == "fields" for w in warnings)

    def test_entity_prd_no_entity(self):
        data = {"entity": None, "fields": []}
        warnings = validate(DocumentType.ENTITY_PRD, data)
        assert any(w.field == "entity" for w in warnings)

    def test_process_document_no_steps(self):
        data = {"process": {"name": "Test"}, "steps": [], "requirements": []}
        warnings = validate(DocumentType.PROCESS_DOCUMENT, data)
        assert any(w.field == "steps" for w in warnings)
        assert any(w.field == "requirements" for w in warnings)

    def test_draft_softens_messages(self):
        data = {"entity": None, "fields": []}
        warnings = validate(DocumentType.ENTITY_PRD, data, is_draft=True)
        assert all("[Draft note]" in w.message for w in warnings)

    def test_validation_does_not_block(self):
        """Validation always returns warnings, never raises."""
        data = {}
        for doc_type in DocumentType:
            warnings = validate(doc_type, data)
            assert isinstance(warnings, list)

    def test_entity_inventory_no_entities(self):
        data = {"entities": []}
        warnings = validate(DocumentType.ENTITY_INVENTORY, data)
        assert any(w.field == "entities" for w in warnings)

    def test_domain_overview_missing_text(self):
        data = {"domain": {"name": "X"}, "domain_overview_text": None, "processes": []}
        warnings = validate(DocumentType.DOMAIN_OVERVIEW, data)
        assert any(w.field == "domain_overview_text" for w in warnings)

    def test_yaml_no_entities(self):
        data = {"entities": []}
        warnings = validate(DocumentType.YAML_PROGRAM_FILES, data)
        assert any(w.field == "entities" for w in warnings)

    def test_crm_eval_no_platform(self):
        data = {"crm_platform": None}
        warnings = validate(DocumentType.CRM_EVALUATION_REPORT, data)
        assert any(w.field == "crm_platform" for w in warnings)
