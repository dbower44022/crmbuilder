"""Drift reconciliation: compare live EspoCRM config against the source YAML
program files and write selected differences back into those files.

This package is one-way (CRM -> YAML); the live CRM is never written to. The
write-back is *surgical*: we never re-serialize a whole file (ruamel normalizes
inline flow-map spacing on dump, which would pollute git diffs and discard
hand-authored column alignment). Instead :class:`YamlDocument` uses ruamel only
to locate the line/column of the target node, then splices replacement text into
the original source bytes so everything we did not touch stays byte-for-byte
identical.

Build phases (see the feature plan): Phase 0 round-trip gate (proven), Phase 1
fields (this is the field write-back core), then relationships, then layouts and
security once the parallel schema-expansion work lands.
"""
from __future__ import annotations

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.locators import (
    FieldLocator,
    LayoutLocator,
    RelationshipLocator,
)
from espo_impl.core.reconcile.patcher import set_field_property

__all__ = [
    "YamlDocument",
    "FieldLocator",
    "RelationshipLocator",
    "LayoutLocator",
    "set_field_property",
]
