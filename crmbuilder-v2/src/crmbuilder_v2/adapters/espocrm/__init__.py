"""EspoCRM engine adapter (PRJ-025 PI-191).

Reads the engine-neutral V2 design records and generates deployable
EspoCRM YAML program files plus a ``MANUAL-CONFIG.md`` deferral
companion. Slice 1 covers ENTITY and FIELD generation; associations,
rules, and the config blocks (savedViews/duplicateChecks/workflows/
emailTemplates) are later slices and surface here as deferral stubs.

The emitted YAML is generated to pass
``espo_impl.core.config_loader.ConfigLoader.validate_program`` — the
adapter runs its own output through that validator as a self-check
(design §10 / REQ-143).
"""

from crmbuilder_v2.adapters.espocrm.adapter import EspoCrmAdapter

__all__ = ["EspoCrmAdapter"]
