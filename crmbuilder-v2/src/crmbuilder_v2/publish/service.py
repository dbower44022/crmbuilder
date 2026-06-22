"""Headless publish service (PRJ-042, PI-243 — REQ-287 + REQ-288).

Ties the existing engines together to push the canonical V2 design to a live
target CRM instance:

1. **Generate** engine YAML from the canonical design, in memory, via the
   PRJ-025 :class:`EspoCrmAdapter` (no files written).
2. **Parse** each generated program into the V1 ``ProgramFile`` model
   (:meth:`ConfigLoader.load_program_from_string`), materializing companion
   ``bodyFile`` support files to a temp dir only when present.
3. **Validate** each program against the engine schema **and the live target
   instance** — ``gather_server_fields`` discovers fields already on the
   target so cross-references resolve (REQ-288), then
   ``validate_program_with_context`` runs the full validator.
4. **Deploy** each valid program through the shared Qt-free
   :func:`deploy_pipeline` using an ``EspoAdminClient`` built from the target
   instance record + its keyring secret.

A ``validate_only`` run stops after step 3. The whole module is Qt-free and
unit-testable: generation, parsing, and validation are separated from the live
target so they can be exercised with fakes; only :func:`publish` touches a real
instance.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from crmbuilder_v2.adapters.base import GenerationResult
from crmbuilder_v2.adapters.espocrm.adapter import EspoCrmAdapter
from crmbuilder_v2.adapters.espocrm.client import DesignClient
from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.deploy_pipeline import deploy_pipeline
from espo_impl.core.field_manager import FieldManager
from espo_impl.core.models import (
    InstanceProfile,
    InstanceRole,
    ProgramContext,
    ProgramFile,
    RunReport,
)
from espo_impl.core.reconcile.live_state import gather_server_fields

OutputFn = Callable[[str, str], None]


@dataclass
class ProgramOutcome:
    """The result of validating (and optionally deploying) one program file.

    :ivar filename: The generated program filename, e.g. ``Contact.yaml``.
    :ivar validation_errors: Validator errors; empty means the program is valid.
    :ivar deployed: Whether this program was applied to the target.
    :ivar report: The deploy :class:`RunReport`, or ``None`` if not deployed.
    :ivar log: Captured ``(message, color)`` deploy log lines.
    """

    filename: str
    validation_errors: list[str] = field(default_factory=list)
    deployed: bool = False
    report: RunReport | None = None
    log: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class PublishResult:
    """The outcome of a publish (or validate-only) run.

    :ivar engine: The target engine identifier (e.g. ``espocrm``).
    :ivar target_instance: The target instance identifier.
    :ivar validate_only: Whether deployment was skipped.
    :ivar preview: Whether this was a non-destructive dry-run (no writes).
    :ivar validation_failed: True if any generated program had validator errors.
    :ivar programs: Per-program outcomes.
    :ivar deferrals: Design constructs the adapter could not express (advisory).
    :ivar manual_config: The MANUAL-CONFIG companion content, if any.
    """

    engine: str
    target_instance: str
    validate_only: bool
    validation_failed: bool
    preview: bool = False
    programs: list[ProgramOutcome] = field(default_factory=list)
    deferrals: list = field(default_factory=list)
    manual_config: str | None = None


def build_target_profile(
    instance_record: dict,
    *,
    api_key: str,
    secret_key: str | None = None,
) -> InstanceProfile:
    """Map a V2 instance record + resolved secrets to an ``InstanceProfile``.

    Mirrors the mapping the ``POST /instances/{id}/audit`` endpoint uses to
    build its introspection client, so the publish target is described the same
    way the audit source is.

    :param instance_record: A V2 ``instance`` record (``instance_*`` keys).
    :param api_key: The resolved API key / password (from the keyring).
    :param secret_key: The resolved HMAC secret key, if any.
    :returns: An ``InstanceProfile`` for ``EspoAdminClient``.
    """
    return InstanceProfile(
        name=(
            instance_record.get("instance_name")
            or instance_record.get("instance_identifier")
            or "target"
        ),
        url=instance_record["instance_url"],
        api_key=api_key,
        auth_method=instance_record.get("instance_auth_method") or "api_key",
        secret_key=secret_key,
        role=InstanceRole.TARGET,
    )


def generate_design_yaml(
    design_client: DesignClient,
    *,
    rendered_at: str,
    engagement: str | None = None,
) -> GenerationResult:
    """Fetch the canonical design and generate engine YAML in memory.

    Replicates the adapter's fetch→generate steps without writing files: the
    nine design lists are read from ``design_client`` and handed to
    :meth:`EspoCrmAdapter.generate`.

    :param design_client: The design source (e.g. ``RestDesignClient``).
    :param rendered_at: ISO timestamp for the generated provenance header.
    :param engagement: Engagement identifier for the provenance header.
    :returns: The in-memory :class:`GenerationResult`.
    """
    adapter = EspoCrmAdapter()
    return adapter.generate(
        design_client.list_entities(),
        design_client.list_fields(),
        design_client.list_engine_overrides(),
        associations=design_client.list_associations(),
        rules=design_client.list_rules(),
        views=design_client.list_views(),
        automations=design_client.list_automations(),
        dedup_rules=design_client.list_dedup_rules(),
        message_templates=design_client.list_message_templates(),
        rendered_at=rendered_at,
        engagement=engagement,
    )


def parse_programs(result: GenerationResult) -> list[tuple[str, ProgramFile]]:
    """Parse a generation result's programs into ``ProgramFile`` objects.

    Companion ``bodyFile`` support files are materialized into a single temp
    directory so email-template references resolve during parsing; the
    directory is removed before returning (body content is captured into the
    model at parse time). When there are no companions, parsing is purely
    in-memory with no disk I/O.

    :param result: The adapter generation result.
    :returns: ``(filename, ProgramFile)`` pairs in generation order.
    """
    loader = ConfigLoader()

    if not result.companions:
        return [
            (a.filename, loader.load_program_from_string(
                a.content, source_name=a.filename
            ))
            for a in result.programs
        ]

    parsed: list[tuple[str, ProgramFile]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        for artifact in result.companions:
            target = root / artifact.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(artifact.content, encoding="utf-8")
        for artifact in result.programs:
            parsed.append((
                artifact.filename,
                loader.load_program_from_string(
                    artifact.content,
                    source_name=artifact.filename,
                    base_dir=root,
                ),
            ))
    return parsed


def validate_programs(
    programs: list[tuple[str, ProgramFile]],
    server_fields_by_entity: dict[str, frozenset[str]] | None = None,
) -> dict[str, list[str]]:
    """Validate parsed programs against the schema + live target fields.

    Builds one cross-program :class:`ProgramContext` (so references resolve
    across the whole batch) seeded with ``server_fields_by_entity`` — the
    fields already present on the live target — then runs the full validator on
    each program. This is the REQ-288 pre-publish gate.

    :param programs: ``(filename, ProgramFile)`` pairs.
    :param server_fields_by_entity: Live-target fields per entity natural name,
        or ``None`` for batch-only validation.
    :returns: ``{filename: [errors]}`` for any program with errors (empty dict
        means every program is valid).
    """
    loader = ConfigLoader()
    context = ProgramContext.from_programs(
        [p for _, p in programs],
        server_fields_by_entity=server_fields_by_entity,
    )
    failures: dict[str, list[str]] = {}
    for filename, program in programs:
        errors = loader.validate_program_with_context(program, context)
        if errors:
            failures[filename] = errors
    return failures


def _entity_names(programs: list[tuple[str, ProgramFile]]) -> list[str]:
    """The natural entity names across all programs (for field discovery)."""
    names: list[str] = []
    for _, program in programs:
        for entity in program.entities:
            if entity.name not in names:
                names.append(entity.name)
    return names


def publish(
    instance_record: dict,
    design_client: DesignClient,
    *,
    api_key: str,
    secret_key: str | None = None,
    rendered_at: str,
    engagement: str | None = None,
    validate_only: bool = False,
    preview: bool = False,
    output_fn: OutputFn | None = None,
) -> PublishResult:
    """Generate, validate, and (unless ``validate_only``) deploy the design.

    :param instance_record: The V2 target ``instance`` record.
    :param design_client: The canonical-design source.
    :param api_key: Resolved target API key / password (from the keyring).
    :param secret_key: Resolved target HMAC secret, if any.
    :param rendered_at: ISO timestamp for the generated provenance header.
    :param engagement: Engagement identifier.
    :param validate_only: If True, stop after validation (deploy nothing).
    :param preview: If True, run a non-destructive dry-run after validation —
        the deploy engine reports the action each object *would* take without
        writing to the target (REQ-289). Ignored when ``validate_only``.
    :param output_fn: Optional deploy log callback; when omitted, each
        program's log is captured into its :class:`ProgramOutcome`.
    :returns: A :class:`PublishResult`.
    """
    target_identifier = (
        instance_record.get("instance_identifier") or "target"
    )
    profile = build_target_profile(
        instance_record, api_key=api_key, secret_key=secret_key
    )
    client = EspoAdminClient(profile)

    result = generate_design_yaml(
        design_client, rendered_at=rendered_at, engagement=engagement
    )
    programs = parse_programs(result)

    server_fields, _warnings = gather_server_fields(
        client, _entity_names(programs)
    )
    failures = validate_programs(programs, server_fields)
    validation_failed = bool(failures)

    pub = PublishResult(
        engine=result.engine,
        target_instance=target_identifier,
        validate_only=validate_only,
        preview=preview,
        validation_failed=validation_failed,
        deferrals=list(result.deferrals),
        manual_config=(
            result.manual_config.content if result.manual_config else None
        ),
    )

    # Validation gate: never touch a program that does not pass its own engine
    # pre-flight (REQ-288). A validate-only run stops here too.
    if validate_only or validation_failed:
        for filename, _program in programs:
            pub.programs.append(
                ProgramOutcome(
                    filename=filename,
                    validation_errors=failures.get(filename, []),
                    deployed=False,
                )
            )
        return pub

    # Deploy, or (preview) dry-run the deploy engine to report planned actions
    # without writing to the target (REQ-289).
    for filename, program in programs:
        log: list[tuple[str, str]] = []
        ofn: OutputFn = output_fn or (
            lambda m, c, _log=log: _log.append((m, c))
        )
        field_mgr = FieldManager(client, FieldComparator(), ofn)
        outcome = deploy_pipeline(program, client, field_mgr, ofn, dry_run=preview)
        pub.programs.append(
            ProgramOutcome(
                filename=filename,
                validation_errors=[],
                deployed=not preview,
                report=outcome.report,
                log=log,
            )
        )
    return pub
