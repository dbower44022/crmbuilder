"""The Operate screens, declared for the segment registry (PI-513 / REQ-591).
``ui.panel_registry`` merges ``PANELS`` and ``ui.main_window`` merges
``ENTITY_TYPE_TO_LABEL``; the per-phase sidebar order stays the shared list
in ``ui.navigation`` by design (DEC-1090).
"""

from __future__ import annotations

from crmbuilder_v2.segments.operate.ui.panels.deploy_history import (
    DeployHistoryPanel,
)
from crmbuilder_v2.segments.operate.ui.panels.instances import InstancesPanel

# Label → factory(client, active_context).
PANELS = {
    "Deploy History": lambda client, _ctx: DeployHistoryPanel(client),
    "Instances": lambda client, _ctx: InstancesPanel(client),
}

# Reference ``entity_type`` values → the panel label that opens them.
ENTITY_TYPE_TO_LABEL = {
    "instance": "Instances",
}
