"""The Operate screens, declared for the segment registry (PI-513 / REQ-591).
``ui.panel_registry`` merges ``PANELS`` and ``ui.main_window`` merges
``ENTITY_TYPE_TO_LABEL``; the per-phase sidebar order stays the shared list
in ``ui.navigation`` by design (DEC-1090).

PI-580 (PRJ-128): the Deployments panel replaces the Instances panel. The
``InstancesPanel`` class and module are retained but no longer registered;
a reference to an ``instance`` opens the Deployments panel, which selects
the deployment holding that connection.
"""

from __future__ import annotations

from crmbuilder_v2.segments.operate.ui.panels.deploy_history import (
    DeployHistoryPanel,
)
from crmbuilder_v2.segments.operate.ui.panels.deployments import DeploymentsPanel

# Label → factory(client, active_context).
PANELS = {
    "Deploy History": lambda client, _ctx: DeployHistoryPanel(client),
    "Deployments": lambda client, ctx: DeploymentsPanel(client, active_context=ctx),
}

# Reference ``entity_type`` values → the panel label that opens them.
ENTITY_TYPE_TO_LABEL = {
    "instance": "Deployments",
}
