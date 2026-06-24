"""Reverse-mapping utilities for CRM audit.

Provides functions to convert EspoCRM API names back to YAML natural
names and to classify entities and fields as custom, native, or system.
"""

from enum import Enum
from typing import Any

from espo_impl.ui.confirm_delete_dialog import NATIVE_ENTITIES


class EntityClass(Enum):
    """Classification of an entity scope."""

    CUSTOM = "custom"
    NATIVE = "native"
    SYSTEM = "system"


class FieldClass(Enum):
    """Classification of a field."""

    CUSTOM = "custom"
    NATIVE = "native"
    SYSTEM = "system"


# System fields that are always excluded from audit output.
SYSTEM_FIELDS: set[str] = {
    "id",
    "deleted",
    "createdAt",
    "modifiedAt",
    "createdById",
    "createdByName",
    "modifiedById",
    "modifiedByName",
    "assignedUserId",
    "assignedUserName",
    "teamsIds",
    "teamsNames",
    "followersIds",
    "followersNames",
    "emailAddressData",
    "phoneNumberData",
    "addressMap",
    "emailAddressIsOptedOut",
    "emailAddressIsInvalid",
    "phoneNumberIsOptedOut",
    "phoneNumberIsInvalid",
    "accountId",
    "accountName",
    "accountIsInactive",
}

# Native fields on Person-type entities (Contact, Lead).
NATIVE_PERSON_FIELDS: set[str] = {
    "salutationName",
    "firstName",
    "lastName",
    "middleName",
    "name",
    "emailAddress",
    "phoneNumber",
    "addressStreet",
    "addressCity",
    "addressState",
    "addressCountry",
    "addressPostalCode",
    "description",
    "title",
    "website",
    "doNotCall",
}

# Native fields on Company-type entities (Account).
NATIVE_COMPANY_FIELDS: set[str] = {
    "name",
    "emailAddress",
    "phoneNumber",
    "website",
    "addressStreet",
    "addressCity",
    "addressState",
    "addressCountry",
    "addressPostalCode",
    "description",
    "sicCode",
    "industry",
    "type",
    "billingAddressStreet",
    "billingAddressCity",
    "billingAddressState",
    "billingAddressCountry",
    "billingAddressPostalCode",
    "shippingAddressStreet",
    "shippingAddressCity",
    "shippingAddressState",
    "shippingAddressCountry",
    "shippingAddressPostalCode",
}

# Native fields on Event-type entities (Meeting, Call).
NATIVE_EVENT_FIELDS: set[str] = {
    "name",
    "status",
    "dateStart",
    "dateEnd",
    "duration",
    "description",
    "parentId",
    "parentType",
    "parentName",
    "accountId",
    "accountName",
    "contactId",
    "contactName",
    "direction",
    "reminders",
    "usersIds",
    "usersNames",
    "contactsIds",
    "contactsNames",
    "leadsIds",
    "leadsNames",
}

# Native fields on Base-type custom entities (minimal set).
NATIVE_BASE_FIELDS: set[str] = {
    "name",
    "description",
}

# Map entity type string to its native fields set.
_TYPE_NATIVE_FIELDS: dict[str, set[str]] = {
    "Person": NATIVE_PERSON_FIELDS,
    "Company": NATIVE_COMPANY_FIELDS,
    "Event": NATIVE_EVENT_FIELDS,
    "Base": NATIVE_BASE_FIELDS,
}

# Entity scopes that are purely internal and should never be audited.
_SYSTEM_SCOPES: set[str] = {
    "Preferences",
    "AuthToken",
    "AuthLogRecord",
    "ScheduledJob",
    "ScheduledJobLogRecord",
    "Job",
    "UniqueId",
    "Currency",
    "PhoneNumber",
    "EmailAddress",
    "Extension",
    "Integration",
    "ExternalAccount",
    "Notification",
    "Note",
    "Portal",
    "PortalRole",
    "PortalUser",
    "Attachment",
    "Role",
    "ActionHistoryRecord",
    "Import",
    "ImportError",
    "LayoutRecord",
    "LayoutSet",
    "Webhook",
    "WebhookEvent",
    "WebhookQueueItem",
    "GroupEmailFolder",
    "EmailFilter",
    "EmailFolder",
    "EmailTemplate",
    "EmailAccount",
    "InboundEmail",
    "Template",
    "WorkingTimeCalendar",
    "WorkingTimeRange",
    "DashboardTemplate",
    "Stream",
    "Subscription",
    "ArrayValue",
    "TwoFactorCode",
    "UserData",
    "AppLogRecord",
    "AuthenticationProvider",
    "EmailAccountScope",
    "EmailTemplateCategory",
    "LeadCapture",
    "LeadCaptureLogRecord",
    "MassEmail",
    "EmailQueueItem",
    "CampaignLogRecord",
    "CampaignTrackingUrl",
    "KnowledgeBaseArticle",
    "KnowledgeBaseCategory",
}


def strip_field_c_prefix(api_name: str, entity_is_native: bool = True) -> str:
    """Reverse the platform c-prefix on a custom field name.

    EspoCRM auto-applies the ``c`` prefix to custom fields ONLY when the
    parent entity is native (Contact, Account, ...). On a *custom* entity
    custom fields keep their natural names with no per-field prefix, so a
    name that legitimately begins with a lowercase ``c`` followed by an
    uppercase letter — e.g. ``cBMValueProvided`` derived from a label
    "CBM Value Provided" — must be left untouched. Stripping it would
    corrupt the field's identity, recreating it on a target under the
    wrong name (REQ-342).

    ``cContactType`` (native entity) → ``contactType``;
    ``cBMValueProvided`` (custom entity) → ``cBMValueProvided`` (unchanged).

    :param api_name: Field name from the EspoCRM API.
    :param entity_is_native: Whether the field's parent entity is native.
        Only then does EspoCRM apply the platform prefix; defaults to
        ``True`` to preserve the historical native-entity behavior for
        callers that have no entity context.
    :returns: YAML natural field name.
    """
    if not entity_is_native:
        return api_name
    if len(api_name) > 1 and api_name[0] == "c" and api_name[1].isupper():
        return api_name[1].lower() + api_name[2:]
    return api_name


def strip_entity_c_prefix(api_name: str) -> str:
    """Reverse the C-prefix on a custom entity name.

    ``CEngagement`` → ``Engagement``,
    ``CSession`` → ``Session``,
    ``CWorkshopAttendance`` → ``WorkshopAttendance``.

    Native entity names are returned unchanged. Names that don't
    follow the ``C{Uppercase}...`` pattern are returned unchanged
    (including names where the second character isn't uppercase,
    which would never be a valid custom entity name).

    :param api_name: Entity name from the EspoCRM API.
    :returns: YAML natural entity name.
    """
    if api_name in NATIVE_ENTITIES:
        return api_name
    if (
        api_name.startswith("C")
        and len(api_name) > 1
        and api_name[1].isupper()
    ):
        return api_name[1:]
    return api_name


def get_yaml_entity_name(espo_name: str) -> str:
    """Map an EspoCRM internal entity name back to the YAML natural name.

    :param espo_name: EspoCRM entity name (e.g., "CEngagement", "Contact").
    :returns: YAML natural name (e.g., "Engagement", "Contact").
    """
    return strip_entity_c_prefix(espo_name)


def classify_entity(
    scope_name: str, scope_meta: dict[str, Any]
) -> EntityClass:
    """Classify an entity scope as custom, native, or system.

    :param scope_name: EspoCRM scope name.
    :param scope_meta: Scope metadata dict from the scopes API.
    :returns: EntityClass classification.
    """
    if scope_name in _SYSTEM_SCOPES:
        return EntityClass.SYSTEM

    if not scope_meta.get("entity", False):
        return EntityClass.SYSTEM

    if not scope_meta.get("customizable", False):
        return EntityClass.SYSTEM

    if scope_meta.get("isCustom", False):
        return EntityClass.CUSTOM

    if scope_name in NATIVE_ENTITIES:
        return EntityClass.NATIVE

    return EntityClass.SYSTEM


def classify_field(
    field_name: str,
    field_meta: dict[str, Any],
    entity_type: str | None = None,
) -> FieldClass:
    """Classify a field as custom, native, or system.

    :param field_name: Field name from the API.
    :param field_meta: Field metadata dict.
    :param entity_type: Entity type string ("Person", "Company", "Base", "Event")
        for native field detection.
    :returns: FieldClass classification.
    """
    if field_name in SYSTEM_FIELDS:
        return FieldClass.SYSTEM

    if field_meta.get("isCustom", False):
        return FieldClass.CUSTOM

    # Heuristic: c-prefix followed by uppercase indicates custom
    if len(field_name) > 1 and field_name[0] == "c" and field_name[1].isupper():
        return FieldClass.CUSTOM

    # Check against entity-type native fields
    if entity_type:
        native_fields = _TYPE_NATIVE_FIELDS.get(entity_type, set())
        if field_name in native_fields:
            return FieldClass.NATIVE

    # Fields not matched are treated as native (default entity fields)
    return FieldClass.NATIVE


def get_native_fields_for_type(entity_type: str | None) -> set[str]:
    """Return the set of native fields for a given entity type.

    :param entity_type: Entity type string.
    :returns: Set of native field names, or empty set if type unknown.
    """
    if entity_type is None:
        return set()
    return _TYPE_NATIVE_FIELDS.get(entity_type, set())
