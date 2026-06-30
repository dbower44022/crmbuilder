"""Foreign field mirrored result-type derivation — PI-378 (REQ-436).

The resolver reads the parent entity's links (link -> target entity) and the
target entity's field list (target field -> type), maps the EspoCRM type to a
neutral result type, and records it on the foreign field — leaving it unset when
the chain does not resolve, never guessing by name-match.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.introspect.reconcile import _resolve_foreign_result_types


class _FakeClient:
    """Returns canned links + field metadata for the resolver."""

    def __init__(self, links, fields):
        self._links = links      # {parent_entity: {link: {"entity": target}}}
        self._fields = fields    # {target_entity: {field_name: {"type": espo_type}}}

    def get_all_links(self, entity):
        return (200, self._links.get(entity, {}))

    def get_entity_field_list(self, entity):
        return (200, self._fields.get(entity, {}))


def _seed_foreign(s, *, link, target):
    ent = entity_repo.create_entity(s, name="MentorProfile", description="d")
    row = field_repo.create_field(
        s,
        field_belongs_to_entity_identifier=ent["entity_identifier"],
        name="postalCode",
        description="mirrored postal code",
        type="foreign",
        foreign_link=link,
        foreign_target=target,
    )
    return row["field_identifier"]


def test_resolves_mirrored_type_from_linked_field(v2_env):
    """REQ-436: a foreign field's result type becomes the mirrored field's type."""
    with session_scope() as s:
        fid = _seed_foreign(s, link="contact", target="addressPostalCode")
        client = _FakeClient(
            links={"MentorProfile": {"contact": {"entity": "Contact"}}},
            fields={"Contact": {"addressPostalCode": {"type": "varchar"}}},
        )
        _resolve_foreign_result_types(
            s, client, [(fid, "MentorProfile", "contact", "addressPostalCode")]
        )
        row = field_repo.get_field(s, fid)
    assert row["field_derived_result_type"] == "text"  # varchar -> text


def test_resolves_non_text_mirrored_type(v2_env):
    """A mirrored number reads as a number, not text."""
    with session_scope() as s:
        fid = _seed_foreign(s, link="account", target="employeeCount")
        client = _FakeClient(
            links={"MentorProfile": {"account": {"entity": "Account"}}},
            fields={"Account": {"employeeCount": {"type": "int"}}},
        )
        _resolve_foreign_result_types(
            s, client, [(fid, "MentorProfile", "account", "employeeCount")]
        )
        row = field_repo.get_field(s, fid)
    assert row["field_derived_result_type"] == "number"


def test_unresolvable_link_leaves_result_type_unset(v2_env):
    """No matching link → no guess; the result type stays null."""
    with session_scope() as s:
        fid = _seed_foreign(s, link="ghost", target="x")
        client = _FakeClient(links={"MentorProfile": {}}, fields={})
        _resolve_foreign_result_types(
            s, client, [(fid, "MentorProfile", "ghost", "x")]
        )
        row = field_repo.get_field(s, fid)
    assert row["field_derived_result_type"] is None


def test_unresolvable_target_field_leaves_result_type_unset(v2_env):
    """Link resolves but the target field is absent → still no guess."""
    with session_scope() as s:
        fid = _seed_foreign(s, link="contact", target="missing")
        client = _FakeClient(
            links={"MentorProfile": {"contact": {"entity": "Contact"}}},
            fields={"Contact": {"somethingElse": {"type": "varchar"}}},
        )
        _resolve_foreign_result_types(
            s, client, [(fid, "MentorProfile", "contact", "missing")]
        )
        row = field_repo.get_field(s, fid)
    assert row["field_derived_result_type"] is None
