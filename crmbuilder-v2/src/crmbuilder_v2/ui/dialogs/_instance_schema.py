"""Compatibility shim (PI-513 / REQ-591): this dialog now lives in the
Operate segment package. Kept for one release; see
segment-package-design.md §4.
"""

import sys as _sys

from crmbuilder_v2.segments.operate.ui.dialogs import _instance_schema as _impl

_sys.modules[__name__] = _impl
