"""Compatibility shim (PI-513 / REQ-591): this repository now lives in the
Operate segment package. Kept for one release; see
segment-package-design.md §4.
"""

import sys as _sys

from crmbuilder_v2.segments.operate.repositories import instances as _impl

_sys.modules[__name__] = _impl
