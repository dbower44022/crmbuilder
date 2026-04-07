"""WorkflowEngine — public API for the CRM Builder Automation Workflow Engine.

Wraps all workflow modules into a single class that Steps 11–16 will call.
Accepts an open sqlite3.Connection in the constructor.
"""

import sqlite3

from automation.workflow.available import get_available_work
from automation.workflow.blocked import block as _block
from automation.workflow.blocked import unblock as _unblock
from automation.workflow.domain_overview import save_domain_overview_text
from automation.workflow.graph import (
    add_domain as _add_domain,
)
from automation.workflow.graph import (
    add_entity as _add_entity,
)
from automation.workflow.graph import (
    add_process as _add_process,
)
from automation.workflow.graph import (
    after_business_object_discovery_import as _after_bod_import,
)
from automation.workflow.graph import (
    after_master_prd_import as _after_master_prd_import,
)
from automation.workflow.graph import (
    create_project as _create_project,
)
from automation.workflow.phases import get_phase
from automation.workflow.status import calculate_status
from automation.workflow.transitions import (
    complete as _complete,
)
from automation.workflow.transitions import (
    revise as _revise,
)
from automation.workflow.transitions import (
    start as _start,
)


class WorkflowEngine:
    """Public API surface for the Workflow Engine.

    All methods operate on the connection provided at construction time.
    Multi-row writes are wrapped in transactions by the underlying modules.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize with an open database connection.

        :param conn: An open sqlite3.Connection to a client database.
        """
        self._conn = conn

    # -- Graph construction --------------------------------------------------

    def create_project(self) -> int:
        """Create the initial project — a single master_prd work item.

        :returns: The master_prd work item id.
        """
        return _create_project(self._conn)

    def after_master_prd_import(self) -> None:
        """Expand the graph after Master PRD import.

        Creates business_object_discovery depending on master_prd.
        """
        _after_master_prd_import(self._conn)

    def after_business_object_discovery_import(self) -> None:
        """Expand the graph after Business Object Discovery import.

        Creates work items for all remaining phases based on current
        Domain, Entity, and Process records.
        """
        _after_bod_import(self._conn)

    def add_entity(self, entity_id: int) -> int:
        """Add a new entity mid-project.

        :param entity_id: The Entity.id for the new entity.
        :returns: The new entity_prd work item id.
        """
        return _add_entity(self._conn, entity_id)

    def add_process(self, process_id: int) -> int:
        """Add a new process mid-project.

        :param process_id: The Process.id for the new process.
        :returns: The new process_definition work item id.
        """
        return _add_process(self._conn, process_id)

    def add_domain(self, domain_id: int) -> list[int]:
        """Add a new domain mid-project.

        :param domain_id: The Domain.id for the new domain.
        :returns: List of created work item ids.
        """
        return _add_domain(self._conn, domain_id)

    # -- Status queries ------------------------------------------------------

    def get_status(self, work_item_id: int) -> str:
        """Return the current stored status of a work item.

        :param work_item_id: The WorkItem.id.
        :returns: The status string.
        :raises ValueError: If the work item is not found.
        """
        row = self._conn.execute(
            "SELECT status FROM WorkItem WHERE id = ?", (work_item_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Work item {work_item_id} not found")
        return row[0]

    def calculate_status(self, work_item_id: int) -> str:
        """Calculate what status a work item should have based on dependencies.

        Returns "ready" or "not_started" based on dependency completeness.
        Does not modify the database.

        :param work_item_id: The WorkItem.id.
        :returns: "ready" or "not_started".
        """
        return calculate_status(self._conn, work_item_id)

    def get_available_work(self) -> list[dict]:
        """Return available work items for the Project Dashboard.

        Returns in_progress items first, then ready items, each group
        ordered by phase then domain sort_order.

        :returns: List of work item dicts.
        """
        return get_available_work(self._conn)

    def get_phase_for(self, work_item_id: int) -> int:
        """Return the phase number for a work item.

        Looks up the item_type and the related Domain's is_service flag,
        then calls get_phase().

        :param work_item_id: The WorkItem.id.
        :returns: The phase number (1–12).
        :raises ValueError: If the work item is not found.
        """
        row = self._conn.execute(
            """
            SELECT wi.item_type, d.is_service
            FROM WorkItem wi
            LEFT JOIN Domain d ON d.id = wi.domain_id
            WHERE wi.id = ?
            """,
            (work_item_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Work item {work_item_id} not found")
        item_type, is_service = row
        return get_phase(item_type, is_service=bool(is_service) if is_service is not None else False)

    # -- Status transitions --------------------------------------------------

    def start(self, work_item_id: int) -> None:
        """Transition a work item from ready to in_progress.

        :param work_item_id: The WorkItem.id.
        :raises ValueError: If the work item is not in status ready.
        """
        _start(self._conn, work_item_id)

    def complete(self, work_item_id: int) -> list[int]:
        """Transition a work item from in_progress to complete.

        Triggers downstream recalculation and automatic unblocking.

        :param work_item_id: The WorkItem.id.
        :returns: List of downstream work item IDs that were affected.
        :raises ValueError: If the work item is not in status in_progress.
        """
        return _complete(self._conn, work_item_id)

    def revise(self, work_item_id: int) -> list[int]:
        """Transition a completed work item back to in_progress for revision.

        Triggers cascade regression on all downstream items.

        :param work_item_id: The WorkItem.id.
        :returns: List of downstream work item IDs that were affected.
        :raises ValueError: If the work item is not in status complete.
        """
        return _revise(self._conn, work_item_id)

    # -- Blocked state -------------------------------------------------------

    def block(self, work_item_id: int, reason: str) -> None:
        """Manually block a work item.

        :param work_item_id: The WorkItem.id.
        :param reason: Free-text reason for blocking.
        :raises ValueError: If the work item cannot be blocked.
        """
        _block(self._conn, work_item_id, reason)

    def unblock(self, work_item_id: int) -> None:
        """Manually unblock a work item.

        :param work_item_id: The WorkItem.id.
        :raises ValueError: If the work item is not blocked.
        """
        _unblock(self._conn, work_item_id)

    # -- Domain Overview -----------------------------------------------------

    def save_domain_overview(self, domain_id: int, text: str) -> None:
        """Save Domain Overview text to the Domain record.

        Called after a domain_overview session is imported.

        :param domain_id: The Domain.id.
        :param text: The generated overview text.
        """
        save_domain_overview_text(self._conn, domain_id, text)
