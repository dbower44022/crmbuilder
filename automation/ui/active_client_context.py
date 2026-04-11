"""Active-client context — Qt wrapper (Section 14.1.3).

Single source of truth for which client the Requirements and Deployment
tabs operate against.  Owns the open SQLite connection to the active
client's database and emits a Qt signal on change.

Delegates pure state transitions to
:class:`automation.core.active_client_state.ActiveClientState`.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime

from PySide6.QtCore import QObject, Signal

from automation.config import preferences
from automation.core.active_client_state import ActiveClientState, Client
from automation.core.client_reachability import check_reachability
from automation.db.migrations import run_client_migrations

logger = logging.getLogger(__name__)


class ActiveClientContext(QObject):
    """Qt-aware active-client context.

    Holds the currently active :class:`Client` row (or None), owns the
    open SQLite connection to the active client's database, and emits
    :attr:`active_client_changed` whenever the active client changes.

    :param master_db_path: Path to the master database.
    :param parent: Parent QObject.
    """

    active_client_changed = Signal(object)

    def __init__(self, master_db_path: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._master_db_path = master_db_path
        self._state = ActiveClientState()
        self._conn: sqlite3.Connection | None = None

    @property
    def client(self) -> Client | None:
        """Return the currently active client, or None."""
        return self._state.client

    @property
    def is_active(self) -> bool:
        """Return True if a client is currently active."""
        return self._state.is_active

    @property
    def connection(self) -> sqlite3.Connection | None:
        """Return the open connection to the active client's database."""
        return self._conn

    def set_active_client(self, client: Client) -> str | None:
        """Activate a client.

        Performs the activation sequence in order:

        1. Reachability check — refuses activation on failure.
        2. Close the previous client's database connection (if any).
        3. Open the new client's database (with migrations).
        4. Update ``Client.last_opened_at`` in the master database.
        5. Persist ``last_selected_client_id`` to preferences.
        6. Emit :attr:`active_client_changed`.

        :param client: The client to activate.
        :returns: None on success, or an error string on failure.
        """
        # Step 1: Reachability check
        result = check_reachability(client.project_folder, client.code)
        if not result.is_reachable:
            return result.error

        # Step 2 & 3: Open new database
        try:
            new_conn = run_client_migrations(client.database_path)
        except Exception as exc:
            return f"Failed to open client database: {exc}"

        # Success path — close old connection
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass

        self._conn = new_conn
        self._state.activate(client)

        # Step 4: Update last_opened_at
        now = datetime.now(UTC).isoformat()
        try:
            master_conn = sqlite3.connect(self._master_db_path)
            try:
                master_conn.execute(
                    "UPDATE Client SET last_opened_at = ? WHERE id = ?",
                    (now, client.id),
                )
                master_conn.commit()
            finally:
                master_conn.close()
            client.last_opened_at = now
        except sqlite3.Error:
            logger.warning("Could not update last_opened_at for client %d", client.id)

        # Step 5: Persist to preferences
        preferences.set_last_selected_client_id(client.id)

        # Step 6: Emit signal
        self.active_client_changed.emit(client)
        return None

    def clear(self) -> None:
        """Deactivate the current client."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

        self._state.clear()
        preferences.set_last_selected_client_id(None)
        self.active_client_changed.emit(None)

    def cleanup(self) -> None:
        """Close database connections on shutdown."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
