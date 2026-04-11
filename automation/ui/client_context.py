"""Client selection state and context propagation.

Pure Python — no PySide6 imports. The Qt layer reads this state
and triggers refreshes when the client changes.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path


@dataclasses.dataclass
class ClientInfo:
    """Immutable snapshot of the selected client.

    :param id: Client.id from the master database.
    :param name: Full client name.
    :param code: Short code (e.g. 'CBM').
    :param database_path: Absolute path to the client's SQLite database.
    """

    id: int
    name: str
    code: str
    database_path: str


class ClientContext:
    """Holds the currently selected client for the Requirements tab.

    All Requirements tab screens read from this context to know
    which client database to query.
    """

    def __init__(self) -> None:
        self._client: ClientInfo | None = None
        self._on_change_callbacks: list = []

    @property
    def client(self) -> ClientInfo | None:
        """Return the currently selected client, or None."""
        return self._client

    @property
    def is_selected(self) -> bool:
        """Return True if a client is currently selected."""
        return self._client is not None

    @property
    def client_name(self) -> str:
        """Return the client name, or empty string if none selected."""
        return self._client.name if self._client else ""

    @property
    def database_path(self) -> str | None:
        """Return the client database path, or None."""
        return self._client.database_path if self._client else None

    def select(self, client: ClientInfo) -> None:
        """Select a new client, resetting all mode state.

        :param client: The client to select.
        """
        self._client = client
        for cb in self._on_change_callbacks:
            cb(client)

    def clear(self) -> None:
        """Clear the current client selection."""
        self._client = None
        for cb in self._on_change_callbacks:
            cb(None)

    def on_change(self, callback) -> None:
        """Register a callback for client changes.

        :param callback: Called with ClientInfo or None when client changes.
        """
        self._on_change_callbacks.append(callback)


def load_clients(master_db_path: str | Path) -> list[ClientInfo]:
    """Load all clients from the master database.

    :param master_db_path: Path to the master database.
    :returns: List of ClientInfo sorted by name.
    """
    conn = sqlite3.connect(str(master_db_path))
    try:
        rows = conn.execute(
            "SELECT id, name, code, database_path FROM Client ORDER BY name"
        ).fetchall()
        return [
            ClientInfo(id=row[0], name=row[1], code=row[2], database_path=row[3])
            for row in rows
        ]
    finally:
        conn.close()
