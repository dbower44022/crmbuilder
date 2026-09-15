"""The segment registry (PI-508 / REQ-591, DEC-1079, DEC-1090).

One rule: a segment package declares, a shared file discovers. This module
holds the only list of segment packages. Adding a segment adds one entry to
``PACKAGES``; adding a record type inside an existing segment adds nothing
here.

Each loader below imports one submodule of every package and reads one
attribute from it, so a shared file pulls in only what it needs and no import
cycle forms between the shared files and the packages:

* ``load_models()``       imports ``<package>.models`` so its tables register
                           on the one ``Base`` (called last by ``access.models``).
* ``router_lists()``      yields each package's ``routers`` tuple.
* ``tool_factories()``    yields each package's ``tool_definitions`` callable.
* ``client_mixins()``     yields each package's desktop-client mixin class.
* ``panel_registries()``  yields each package's ``PANELS`` mapping.
* ``entity_type_labels()`` yields each package's ``ENTITY_TYPE_TO_LABEL``.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any

# The one list. Order is the order contributions are assembled in.
PACKAGES: tuple[str, ...] = (
    "crmbuilder_v2.segments.client_management",
    "crmbuilder_v2.segments.operate",
)


def _attribute(submodule: str, name: str) -> Iterator[Any]:
    for package in PACKAGES:
        module = importlib.import_module(f"{package}.{submodule}")
        yield getattr(module, name)


def load_models() -> None:
    """Import every package's ``models`` module so its tables register."""
    for package in PACKAGES:
        importlib.import_module(f"{package}.models")


def router_lists() -> Iterator[tuple]:
    return _attribute("routers", "routers")


def tool_factories() -> Iterator[Any]:
    return _attribute("tools", "tool_definitions")


def client_mixins() -> tuple[type, ...]:
    return tuple(_attribute("client", "MIXIN"))


def panel_registries() -> Iterator[dict]:
    return _attribute("ui", "PANELS")


def entity_type_labels() -> Iterator[dict]:
    return _attribute("ui", "ENTITY_TYPE_TO_LABEL")
