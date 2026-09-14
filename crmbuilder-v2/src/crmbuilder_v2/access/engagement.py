"""Compatibility shim (PI-508 / REQ-591): this module now lives in the
Client Management segment package. The import path is kept for one release
so every existing import keeps resolving to the same module object;
remove with the other shims listed in segment-package-design.md §4.
"""

import sys as _sys

from crmbuilder_v2.segments.client_management.repositories import (
    engagement as _impl,
)

_sys.modules[__name__] = _impl
