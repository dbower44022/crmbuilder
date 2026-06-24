"""Tests for the native-only field c-prefix reversal (REQ-342 / PI-307).

EspoCRM applies the platform ``c`` prefix to custom fields only on native
entities; on custom entities fields keep their natural names. The reverse
mapper must therefore strip only for native entities, or it corrupts a
field name that legitimately begins with c+Uppercase (e.g.
``cBMValueProvided`` from a "CBM ..." label) into ``bMValueProvided``.
"""

import pytest

from espo_impl.core.audit_utils import strip_field_c_prefix


@pytest.mark.parametrize(
    ("api_name", "is_native", "expected"),
    [
        ("cContactType", True, "contactType"),   # native: prefix stripped
        ("cMentorStatus", True, "mentorStatus"),
        ("cBMValueProvided", False, "cBMValueProvided"),  # custom: untouched
        ("cContactType", False, "cContactType"),          # custom: untouched
        ("amount", False, "amount"),                      # natural name
        ("cBMValueProvided", True, "bMValueProvided"),    # native strip rule
        ("c", True, "c"),                                 # too short
        ("created", True, "created"),                     # c not + uppercase
    ],
)
def test_strip_field_c_prefix_native_only(
    api_name: str, is_native: bool, expected: str
) -> None:
    assert strip_field_c_prefix(api_name, entity_is_native=is_native) == expected


def test_default_is_native_for_backward_compatibility():
    # Callers with no entity context get the historical native behavior.
    assert strip_field_c_prefix("cContactType") == "contactType"
