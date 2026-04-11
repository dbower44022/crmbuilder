"""Deployment guidance messages (Section 14.9.2).

Pure Python — no PySide6 imports.

Provides guidance text for work items that are performed outside
the Requirements tab (crm_deployment, crm_configuration, verification).
"""

from __future__ import annotations

# Work item types that are performed in the Deployment tab
DEPLOYMENT_WORK_ITEM_TYPES = {
    "crm_deployment",
    "crm_configuration",
    "verification",
}

GUIDANCE_MESSAGES: dict[str, str] = {
    "crm_deployment": (
        "This work item covers CRM instance deployment, which is performed in "
        "the Deployment tab. Switch to the Deployment tab to provision and configure "
        "the CRM instance. Once deployment is complete, return here to mark "
        "this work item as complete."
    ),
    "crm_configuration": (
        "This work item covers CRM configuration, which is performed in "
        "the Deployment tab using YAML program files. Switch to the Deployment tab, "
        "select the program files, and run them against the CRM instance. "
        "Once configuration is verified, return here to mark this work item "
        "as complete."
    ),
    "verification": (
        "This work item covers post-deployment verification. Switch to "
        "the Deployment tab and use the Verify action to confirm that the CRM "
        "instance matches the expected configuration. Once verification "
        "passes, return here to mark this work item as complete."
    ),
}


def is_deployment_work_item(item_type: str) -> bool:
    """Check if a work item type is performed in the Deployment tab.

    :param item_type: The WorkItem.item_type value.
    :returns: True if this is a deployment/configuration/verification work item.
    """
    return item_type in DEPLOYMENT_WORK_ITEM_TYPES


def get_guidance_message(item_type: str) -> str | None:
    """Get the deployment guidance message for a work item type.

    :param item_type: The WorkItem.item_type value.
    :returns: Guidance message string, or None if not a deployment work item.
    """
    return GUIDANCE_MESSAGES.get(item_type)
