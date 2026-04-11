"""Pure-Python active-client state (no Qt dependencies).

Holds the ``Client`` model and ``ActiveClientState`` which tracks which
client is currently active across the application.  The Qt wrapper in
``automation.ui.active_client_context`` delegates to this module for
all state transitions so they are unit-testable without PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Client:
    """Full client row from the master database.

    :param id: Primary key.
    :param name: Display name.
    :param code: Short code (2-10 uppercase alphanumeric, starts with letter).
    :param description: Free-text description.
    :param project_folder: Absolute path to the client's project folder.
    :param crm_platform: CRM platform (e.g. ``'EspoCRM'``), or None.
    :param deployment_model: Deployment model, or None.
    :param last_opened_at: ISO timestamp of last activation, or None.
    :param created_at: ISO timestamp of creation, or None.
    :param updated_at: ISO timestamp of last update, or None.
    """

    id: int
    name: str
    code: str
    description: str | None
    project_folder: str
    crm_platform: str | None = None
    deployment_model: str | None = None
    last_opened_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def database_path(self) -> str:
        """Derive the client database path from project_folder and code."""
        return f"{self.project_folder}/.crmbuilder/{self.code}.db"


class ActiveClientState:
    """Pure-Python state holder for the active client.

    Tracks the currently active client (or None).  Does not own any
    database connections or Qt objects — those belong to the Qt wrapper.
    """

    def __init__(self) -> None:
        self._client: Client | None = None

    @property
    def client(self) -> Client | None:
        """Return the currently active client, or None."""
        return self._client

    @property
    def is_active(self) -> bool:
        """Return True if a client is currently active."""
        return self._client is not None

    def activate(self, client: Client) -> None:
        """Set the active client.

        :param client: The client to activate.
        """
        self._client = client

    def clear(self) -> None:
        """Clear the active client."""
        self._client = None
