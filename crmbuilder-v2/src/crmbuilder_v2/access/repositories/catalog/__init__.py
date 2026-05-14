"""Catalog access layer (catalog-ingestion-PRD-v0.1.md sections 5 and 6).

Split into ``read``, ``write``, and ``exports`` modules; the package's
``__init__`` re-exports the public symbols so importing
``catalog.list_entities`` works without callers having to know which
sub-module the function lives in.
"""

from __future__ import annotations

from crmbuilder_v2.access.repositories.catalog import read

list_entities = read.list_entities
get_entity = read.get_entity
get_attribute = read.get_attribute
search = read.search
cross_system_map = read.cross_system_map
gap_check = read.gap_check

__all__ = [
    "list_entities",
    "get_entity",
    "get_attribute",
    "search",
    "cross_system_map",
    "gap_check",
]
