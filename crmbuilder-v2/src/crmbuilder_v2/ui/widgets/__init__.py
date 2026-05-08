"""Reusable UI widgets used by panels and dialogs.

Added in v2-ui-v0.2-A. Each widget is composed by panels and CRUD
dialogs but does not depend on either; the dependency direction is
strictly widgets ← (panels, dialogs).
"""

from crmbuilder_v2.ui.widgets.date_field import DateField
from crmbuilder_v2.ui.widgets.hierarchical_picker import HierarchicalEntityPicker
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

__all__ = ["DateField", "HierarchicalEntityPicker", "ReferencesSection"]
