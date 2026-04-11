"""Tests for automation.ui.mode_integration — pure Python."""


from automation.ui.mode_integration.deployment_guidance import (
    get_guidance_message,
    is_deployment_work_item,
)
from automation.ui.mode_integration.instance_association import (
    find_client_for_instance,
    find_instance_for_client,
)
from automation.ui.mode_integration.mode_transition import (
    should_auto_select_on_mode_change,
)

# ---------------------------------------------------------------------------
# deployment_guidance tests
# ---------------------------------------------------------------------------


class TestDeploymentGuidance:

    def test_crm_deployment_is_deployment(self):
        assert is_deployment_work_item("crm_deployment")

    def test_crm_configuration_is_deployment(self):
        assert is_deployment_work_item("crm_configuration")

    def test_verification_is_deployment(self):
        assert is_deployment_work_item("verification")

    def test_master_prd_is_not_deployment(self):
        assert not is_deployment_work_item("master_prd")

    def test_guidance_message_exists(self):
        msg = get_guidance_message("crm_deployment")
        assert msg is not None
        assert "Deployment tab" in msg

    def test_no_guidance_for_normal_item(self):
        msg = get_guidance_message("entity_prd")
        assert msg is None


# ---------------------------------------------------------------------------
# instance_association tests
# ---------------------------------------------------------------------------


class _FakeProfile:
    """Minimal fake of InstanceProfile for testing."""
    def __init__(self, name: str, project_folder: str | None = None):
        self.name = name
        self.project_folder = project_folder


class _FakeClient:
    """Minimal fake of ClientInfo for testing."""
    def __init__(self, database_path: str):
        self.database_path = database_path


class TestFindInstanceForClient:

    def test_finds_match_by_name(self):
        profiles = [_FakeProfile("CBM"), _FakeProfile("TestCRM")]
        idx = find_instance_for_client("CBM", profiles)
        assert idx == 0

    def test_case_insensitive(self):
        profiles = [_FakeProfile("TestCRM")]
        idx = find_instance_for_client("testcrm", profiles)
        assert idx == 0

    def test_no_match(self):
        profiles = [_FakeProfile("Other")]
        idx = find_instance_for_client("CBM", profiles)
        assert idx is None

    def test_none_platform(self):
        profiles = [_FakeProfile("CBM")]
        idx = find_instance_for_client(None, profiles)
        assert idx is None

    def test_empty_profiles(self):
        idx = find_instance_for_client("CBM", [])
        assert idx is None


class TestFindClientForInstance:

    def test_finds_match_by_path(self, tmp_path):
        project_folder = str(tmp_path / "project")
        db_path = str(tmp_path / "project" / "data" / "client.db")
        clients = [_FakeClient(db_path)]
        idx = find_client_for_instance(project_folder, clients)
        assert idx == 0

    def test_no_match(self, tmp_path):
        project_folder = str(tmp_path / "project_a")
        clients = [_FakeClient(str(tmp_path / "project_b" / "client.db"))]
        idx = find_client_for_instance(project_folder, clients)
        assert idx is None

    def test_none_folder(self):
        clients = [_FakeClient("/some/path")]
        idx = find_client_for_instance(None, clients)
        assert idx is None


# ---------------------------------------------------------------------------
# mode_transition tests
# ---------------------------------------------------------------------------


class TestModeTransition:

    def test_auto_select_when_selection_exists(self):
        assert should_auto_select_on_mode_change("requirements", True)

    def test_no_auto_select_without_selection(self):
        assert not should_auto_select_on_mode_change("requirements", False)
