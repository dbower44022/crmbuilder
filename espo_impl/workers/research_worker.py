"""Background worker thread for CRM platform research."""

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from espo_impl.core.platform_researcher import PlatformResearcher


class ResearchWorker(QThread):
    """Background worker that researches a CRM platform.

    :param api_key: Anthropic API key.
    :param url: CRM platform URL to research.
    :param base_dir: Project root directory.
    :param existing_yaml: Existing YAML content if updating.
    :param api_docs_url: Optional API documentation URL.
    :param parent: Parent QObject.
    """

    output_line = Signal(str, str)
    finished_ok = Signal(object)
    finished_error = Signal(str)

    def __init__(
        self,
        api_key: str,
        url: str,
        base_dir: Path,
        existing_yaml: str | None = None,
        api_docs_url: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api_key = api_key
        self._url = url
        self._base_dir = base_dir
        self._existing_yaml = existing_yaml
        self._api_docs_url = api_docs_url

    def run(self) -> None:
        """Execute the platform research in a background thread."""
        try:
            researcher = PlatformResearcher(
                api_key=self._api_key,
                schema_path=self._base_dir / "docs" / "crm-platforms" / "schema.yaml",
                example_path=self._base_dir / "docs" / "crm-platforms" / "platforms" / "espocrm.yaml",
                platforms_dir=self._base_dir / "docs" / "crm-platforms" / "platforms",
                callback=self.output_line.emit,
            )
            result = researcher.research(
                self._url, self._existing_yaml, self._api_docs_url
            )
            if result.success:
                self.finished_ok.emit(result)
            else:
                self.finished_error.emit(result.error)
        except Exception as exc:
            self.finished_error.emit(f"Unexpected error: {exc}")
