"""Catalog access layer (catalog-ingestion-PRD-v0.1.md sections 5 and 6).

Split into ``read`` and ``write`` modules; the package's ``__init__``
re-exports the public symbols so importing ``catalog.list_entities`` works
without callers having to know which sub-module the function lives in.
(PI-β slice 4 removed the per-entity JSON ``exports`` module with the rest
of the snapshot machinery.)
"""

from __future__ import annotations

from crmbuilder_v2.access.repositories.catalog import read, write

# read
list_entities = read.list_entities
get_entity = read.get_entity
get_attribute = read.get_attribute
search = read.search
cross_system_map = read.cross_system_map
gap_check = read.gap_check

# write
create_entity = write.create_entity
update_entity = write.update_entity
patch_entity = write.patch_entity
delete_entity = write.delete_entity
create_attribute = write.create_attribute
update_attribute = write.update_attribute
patch_attribute = write.patch_attribute
delete_attribute = write.delete_attribute

__all__ = [
    "list_entities",
    "get_entity",
    "get_attribute",
    "search",
    "cross_system_map",
    "gap_check",
    "create_entity",
    "update_entity",
    "patch_entity",
    "delete_entity",
    "create_attribute",
    "update_attribute",
    "patch_attribute",
    "delete_attribute",
]
