"""Pluggable CRM engine-adapter framework (PRJ-025 PI-191 slice 1).

The V2 database is the engine-neutral source of truth for CRM design
(``engine-neutral-design-model-and-adapters.md`` §1–§3). A **CRM
adapter** reads those design records and *generates* the deployable
artifact for one target engine — deriving engine mechanics, applying
engine defaults, merging a sparse engine-scoped override layer, and
emitting loud deferral stubs for anything not yet capturable (§10).

This module fixes the minimal-but-real adapter contract. The EspoCRM
adapter (``adapters/espocrm``) is the first backend; later slices add
its associations/rules/config blocks, and later PIs add other engines
(HubSpot). The contract is deliberately small here — slices 2/3 grow
the construct set the adapter renders, not this protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Deferral:
    """One design construct (or attribute) the adapter did not emit.

    Deferrals never silently drop intent (§10): each one is surfaced in
    the generated ``MANUAL-CONFIG.md`` companion so an operator can
    complete the configuration by hand or wait for the slice that
    captures it. ``kind`` groups the deferral; ``identifier`` is the
    source design record (``ENT-``/``FLD-``/``OVR-`` or ``-`` when the
    deferral is a whole construct class); ``detail`` is the human reason.
    """

    kind: str
    identifier: str
    name: str
    parent: str | None
    detail: str


@dataclass(frozen=True)
class ProgramArtifact:
    """One generated engine program file — its name and serialized body."""

    filename: str
    content: str


@dataclass
class GenerationResult:
    """Everything one ``generate`` produced: the program files, the
    deferral companion, and the deferral records that built it.

    Pure and deterministic: two generations from the same design records
    (same ``rendered_at``) compare equal byte-for-byte.
    """

    engine: str
    rendered_at: str
    programs: list[ProgramArtifact] = field(default_factory=list)
    manual_config: ProgramArtifact | None = None
    deferrals: list[Deferral] = field(default_factory=list)


@runtime_checkable
class CrmAdapter(Protocol):
    """The per-engine backend contract (design §10).

    An adapter ``generate``s the deployable artifact set for its engine
    from the engine-neutral design records. ``engine`` is the closed-set
    engine key (``"espocrm"``, ``"hubspot"``, …) matching
    ``vocab.TARGET_ENGINES`` — the same key an ``engine_override`` scopes
    to, so the adapter knows which override rows to merge.
    """

    engine: str

    def generate(
        self,
        entities: list[dict],
        fields: list[dict],
        overrides: list[dict],
        *,
        rendered_at: str,
        engagement: str | None = None,
    ) -> GenerationResult:
        """Produce the engine artifact set from the neutral design records.

        :param entities: ``entity`` design records (engine-neutral).
        :param fields: ``field`` design records, each carrying its
            embedded ``field_options`` and a ``parent_entity_identifier``.
        :param overrides: ``engine_override`` records (all engines; the
            adapter merges only the ones scoped to ``self.engine``).
        :param rendered_at: injected ISO timestamp (determinism — never
            read the clock inside the pure build).
        :param engagement: the source engagement label, for provenance.
        :returns: the :class:`GenerationResult`.
        """
        ...
