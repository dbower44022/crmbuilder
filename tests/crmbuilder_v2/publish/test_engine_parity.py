"""The two engines do the same thing to an instance (PI-532 / REQ-618).

The publish path is about to stop calling version 1 and start calling version
2. The service's own tests cannot prove that changed nothing: they work by
replacing version 1's functions, so they disappear with them.

This does the only check that actually answers the question. One declaration,
two engines, two identical fake instances — then compare what each engine
*wrote*. Not the report, not the return value: the calls, and the bodies they
carried. If version 2 sends the same writes as version 1, a live instance
cannot tell the difference.

Order deliberately is not compared. Version 1 works through one object type at
a time; version 2 does every object type's fields, then every object type's
layouts. Both orders are safe — what must not differ is the content.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from crmbuilder_v2.publish.declaration import parse
from crmbuilder_v2.publish.from_declaration import plan_for
from crmbuilder_v2.publish.run import apply_plan

from espo_impl.core.comparator import FieldComparator
from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.deploy_pipeline import deploy_pipeline
from espo_impl.core.field_manager import FieldManager

#: One object type with the things a real design carries: a created entity,
#: its settings, two fields of different kinds, a record view and a list view,
#: and a link to a platform object type.
DECLARATION = """
version: "1.0.0"
content_version: "1.0.0"
entities:
  Engagement:
    action: create
    type: Base
    description: A mentoring engagement
    settings:
      labelSingular: Engagement
      labelPlural: Engagements
      stream: true
    fields:
      - name: stage
        type: enum
        label: Stage
        options: ["Active", "Closed"]
        required: true
      - name: summary
        type: text
        label: Summary
        maxLength: 500
    layout:
      detail:
        panels:
          - label: Overview
            rows: [[{name: stage}, {name: summary}]]
      list:
        columns: [{field: stage}, {field: summary, width: 30}]
relationships:
  - entity: Engagement
    entityForeign: Account
    link: account
    linkForeign: engagements
    linkType: manyToOne
    label: Account
    labelForeign: Engagements
"""

#: The calls that change the instance. Everything else is a read.
WRITES = frozenset(
    {
        "create_entity",
        "remove_entity",
        "update_entity",
        "create_field",
        "update_field",
        "save_layout",
        "create_link",
        "rebuild",
    }
)


class RecordingInstance:
    """An instance that answers as an empty one and remembers every call.

    Both engines drive it: the method names are the same, because version 2's
    write client kept version 1's names precisely so the managers could be
    absorbed without translation.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.entities: set[str] = set()
        # Version 1's report header reads these off the client it was given.
        self.profile = type(
            "Profile",
            (),
            {"api_url": "https://x/api/v1", "url": "https://x", "name": "x"},
        )()

    # --- reads ---
    def check_entity_exists(self, name: str) -> tuple[int, bool]:
        return 200, name in self.entities

    def get_entity_full_metadata(self, name: str) -> tuple[int, Any]:
        return (200, {"fields": {}}) if name in self.entities else (404, None)

    def get_entity_defs(self, name: str) -> tuple[int, Any]:
        return self.get_entity_full_metadata(name)

    def get_client_defs(self, name: str) -> tuple[int, Any]:
        return 200, {}

    def get_field(self, entity: str, name: str) -> tuple[int, Any]:
        return 404, None

    def get_entity_field_list(self, entity: str) -> tuple[int, Any]:
        return 404, None

    def get_layout(self, entity: str, layout_type: str) -> tuple[int, Any]:
        return 200, []

    def get_link(self, entity: str, link: str) -> tuple[int, Any]:
        return 404, None

    def get_all_links(self, entity: str) -> tuple[int, Any]:
        return 200, {}

    def get_metadata(self, key: str) -> tuple[int, Any]:
        return 200, {}

    def get_all_scopes(self) -> tuple[int, Any]:
        return 200, {"Account": {}, "CEngagement": {}}

    # --- writes ---
    def create_entity(self, payload: dict) -> tuple[int, Any]:
        self.calls.append(("create_entity", dict(payload)))
        self.entities.add(f"C{payload['name']}")
        return 200, {}

    def remove_entity(self, name: str) -> tuple[int, Any]:
        self.calls.append(("remove_entity", name))
        return 200, {}

    def update_entity(self, payload: dict) -> tuple[int, Any]:
        self.calls.append(("update_entity", dict(payload)))
        return 200, {}

    def create_field(self, entity: str, payload: dict) -> tuple[int, Any]:
        self.calls.append(("create_field", (entity, dict(payload))))
        return 200, {}

    def update_field(self, entity: str, name: str, payload: dict) -> tuple[int, Any]:
        self.calls.append(("update_field", (entity, name, dict(payload))))
        return 200, {}

    def save_layout(self, entity: str, layout_type: str, body: Any):
        self.calls.append(("save_layout", (entity, layout_type, body)))
        return 200, {}

    def create_link(self, payload: dict) -> tuple[int, Any]:
        self.calls.append(("create_link", dict(payload)))
        return 200, {}

    def rebuild(self) -> tuple[int, Any]:
        self.calls.append(("rebuild", None))
        return 200, {}

    def writes(self) -> list[tuple[str, Any]]:
        return [call for call in self.calls if call[0] in WRITES]


def _version_one() -> RecordingInstance:
    instance = RecordingInstance()
    program = ConfigLoader().load_program_from_string(
        DECLARATION, source_name="Engagement.yaml"
    )
    log: list[tuple[str, str]] = []
    deploy_pipeline(
        program,
        instance,
        FieldManager(instance, FieldComparator(), lambda m, c: log.append((m, c))),
        lambda m, c: log.append((m, c)),
        dry_run=False,
    )
    return instance


def _version_two() -> RecordingInstance:
    instance = RecordingInstance()
    declaration = parse(DECLARATION, "Engagement.yaml")
    apply_plan(instance, plan_for([declaration]), wait_timeout_seconds=0.1)
    return instance


@pytest.fixture(scope="module")
def engines() -> tuple[list, list]:
    return _version_one().writes(), _version_two().writes()


def _of(kind: str, writes: list[tuple[str, Any]]) -> list[Any]:
    return [payload for name, payload in writes if name == kind]


def _readable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


# --- the object type --------------------------------------------------------


def test_both_engines_create_the_object_type_the_same_way(engines) -> None:
    one, two = engines
    assert _of("create_entity", one) == _of("create_entity", two)


def test_both_engines_rebuild_the_cache_after_creating_one(engines) -> None:
    one, two = engines
    assert bool(_of("rebuild", one)) == bool(_of("rebuild", two))


def test_both_engines_write_the_same_object_settings(engines) -> None:
    one, two = engines
    assert _readable(_of("update_entity", one)) == _readable(_of("update_entity", two))


# --- fields -----------------------------------------------------------------


def test_both_engines_create_the_same_fields(engines) -> None:
    one, two = engines
    assert sorted(map(_readable, _of("create_field", one))) == sorted(
        map(_readable, _of("create_field", two))
    )


def test_neither_engine_updates_a_field_on_an_empty_instance(engines) -> None:
    one, two = engines
    assert _of("update_field", one) == _of("update_field", two) == []


# --- layouts and links ------------------------------------------------------


def test_both_engines_write_the_same_layouts(engines) -> None:
    one, two = engines
    assert sorted(map(_readable, _of("save_layout", one))) == sorted(
        map(_readable, _of("save_layout", two))
    )


def test_both_engines_create_the_same_link(engines) -> None:
    one, two = engines
    assert _readable(_of("create_link", one)) == _readable(_of("create_link", two))


# --- and nothing else ------------------------------------------------------


def test_neither_engine_writes_anything_the_other_does_not(engines) -> None:
    one, two = engines
    assert sorted(name for name, _ in one) == sorted(name for name, _ in two)
