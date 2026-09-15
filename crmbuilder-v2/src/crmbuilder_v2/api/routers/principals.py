"""Compatibility shim (PI-508 / REQ-591): this router now lives in the
Client Management segment package. Kept for one release; see
segment-package-design.md §4.
"""

import sys as _sys

from crmbuilder_v2.segments.client_management.routers import principals as _impl

_sys.modules[__name__] = _impl
