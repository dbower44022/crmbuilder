"""EspoCRM introspection package for CRMBuilder V2.

Ported from V1 ``espo_impl.core`` for PI-187. This package provides a
standalone, Qt-free toolkit for reading the configuration of a live
EspoCRM instance — a pure ``requests``-based REST client plus the
catalogs and helpers needed to classify and de-prefix the discovered
entities and fields back into their YAML-natural form.

Public surface:

* :class:`~crmbuilder_v2.introspect.espo_client.EspoIntrospectionClient`
  and :class:`~crmbuilder_v2.introspect.espo_client.EspoConnectionConfig`
  — the connection/auth + discovery/security REST client.
* The catalogs, enums, and helpers in
  :mod:`crmbuilder_v2.introspect.audit_utils`.
* :data:`~crmbuilder_v2.introspect.native_entity_types.NATIVE_ENTITY_BASE_TYPE`
  and :func:`~crmbuilder_v2.introspect.native_entity_types.get_base_type`.
"""

from __future__ import annotations

from crmbuilder_v2.introspect.audit_utils import (
    NATIVE_BASE_FIELDS,
    NATIVE_COMPANY_FIELDS,
    NATIVE_ENTITIES,
    NATIVE_EVENT_FIELDS,
    NATIVE_PERSON_FIELDS,
    SYSTEM_FIELDS,
    EntityClass,
    FieldClass,
    classify_entity,
    classify_field,
    get_native_fields_for_type,
    get_yaml_entity_name,
    strip_entity_c_prefix,
    strip_field_c_prefix,
)
from crmbuilder_v2.introspect.espo_client import (
    EspoConnectionConfig,
    EspoIntrospectionClient,
    format_error_detail,
)
from crmbuilder_v2.introspect.native_entity_types import (
    NATIVE_ENTITY_BASE_TYPE,
    get_base_type,
)

__all__ = [
    # client
    "EspoIntrospectionClient",
    "EspoConnectionConfig",
    "format_error_detail",
    # audit catalogs / helpers
    "SYSTEM_FIELDS",
    "NATIVE_PERSON_FIELDS",
    "NATIVE_COMPANY_FIELDS",
    "NATIVE_EVENT_FIELDS",
    "NATIVE_BASE_FIELDS",
    "NATIVE_ENTITIES",
    "EntityClass",
    "FieldClass",
    "strip_field_c_prefix",
    "strip_entity_c_prefix",
    "get_yaml_entity_name",
    "classify_entity",
    "classify_field",
    "get_native_fields_for_type",
    # native entity base types
    "NATIVE_ENTITY_BASE_TYPE",
    "get_base_type",
]
