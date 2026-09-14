"""Compatibility shim (PI-508 / REQ-591): this dialog now lives in the
Client Management segment package. Kept for one release; see
segment-package-design.md §4.
"""

import sys as _sys

from crmbuilder_v2.segments.client_management.ui.dialogs import (
    _engagement_schema as _impl,
)

_sys.modules[__name__] = _impl
