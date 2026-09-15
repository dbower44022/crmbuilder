"""The request-schema base and the inline governance edge (PI-513 / REQ-591).

Split out of ``api.schemas`` so a segment package's schemas can build on the
same base and carry inline edges without importing the shared module, which
would form an import cycle (the shared module re-exports every package's
schemas). ``api.schemas`` re-exports both names.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GovernanceEdgeIn(_Base):
    """A fully-specified references-table edge supplied inline on a governance
    create/update body. The access layer creates these in the same
    transaction so edge-required rules see them at commit time."""

    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship: str
