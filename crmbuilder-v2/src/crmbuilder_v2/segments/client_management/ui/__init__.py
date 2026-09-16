"""The Client Management screens, declared for the segment registry
(PI-508 / REQ-591). ``ui.panel_registry`` merges ``PANELS`` and
``ui.main_window`` merges ``ENTITY_TYPE_TO_LABEL``; the per-phase sidebar
order stays the shared list in ``ui.navigation`` by design (DEC-1090).
"""

from __future__ import annotations

from crmbuilder_v2.segments.client_management.ui.panels.clients import (
    ClientsPanel,
)
from crmbuilder_v2.segments.client_management.ui.panels.engagements import (
    EngagementsPanel,
)
from crmbuilder_v2.segments.client_management.ui.panels.participant import (
    ParticipantsPanel,
)

# Label → factory(client, active_context). Engagements takes the active
# context so the picker and the top strip follow the selection.
PANELS = {
    "Clients": lambda client, _ctx: ClientsPanel(client),
    "Engagements": lambda client, ctx: EngagementsPanel(client, active_context=ctx),
    "Participants": lambda client, _ctx: ParticipantsPanel(client),
}

# Reference ``entity_type`` values → the panel label that opens them.
ENTITY_TYPE_TO_LABEL = {
    "client": "Clients",
    "engagement": "Engagements",
    "participant": "Participants",
}
