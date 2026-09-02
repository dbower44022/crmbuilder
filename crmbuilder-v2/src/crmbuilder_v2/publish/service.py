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

from crmbuilder_v2.access.apply_plan import fingerprint_plan, screen_automatic
from crmbuilder_v2.adapters.base import GenerationResult
from crmbuilder_v2.adapters.espocrm.adapter import EspoCrmAdapter
from crmbuilder_v2.adapters.espocrm.client import DesignClient
from crmbuilder_v2.publish.backup import BackupCaptureError, capture_target_backup
from crmbuilder_v2.publish.live_state import gather_server_fields
from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.deploy_pipeline import deploy_pipeline
from espo_impl.core.field_manager import FieldManager
from espo_impl.core.models import (
    EntityAction,
    InstanceProfile,
    InstanceRole,
    ProgramContext,
    ProgramFile,
    RunReport,
    SettingsResult,
    SettingsStatus,
)
from espo_impl.core.system_settings_manager import (
    SystemSettingsManager,
    SystemSettingsManagerError,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

OutputFn = Callable[[str, str], None]


@dataclass
class ProgramOutcome:
    """The result of validating (and optionally deploying) one program file.

    :ivar filename: The generated program filename, e.g. ``Contact.yaml``.
    :ivar validation_errors: Validator errors; empty means the program is valid.
    :ivar deployed: Whether this program was applied to the target.
    :ivar report: The deploy :class:`RunReport`, or ``None`` if not deployed.
    :ivar log: Captured ``(message, color)`` deploy log lines.
    :ivar entities: Natural entity names this program declares.
    :ivar field_names: Field names this program declares, across its entities,
        de-duplicated in first-seen order.
    :ivar relationship_count: Link relationships this program declares.
    """

    filename: str
    validation_errors: list[str] = field(default_factory=list)
    deployed: bool = False
    report: RunReport | None = None
    log: list[tuple[str, str]] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    field_names: list[str] = field(default_factory=list)
    relationship_count: int = 0

    @classmethod
    def for_program(
        cls, filename: str, program: ProgramFile, **kwargs
    ) -> ProgramOutcome:
        """Build an outcome stamped with what the program actually declares.

        Every outcome carries this census, on every path — validate-only,
        validation failure, abort, and deploy alike — because a caller has no
        other way to tell a program that generated its objects from one that
        generated an empty shell. A publish whose design lost the field-to-entity
        edges still produces one program per entity and still validates clean
        (REQ-483): the count is the only signal that anything is missing.
        """
        names: list[str] = []
        for entity in program.entities:
            for fld in entity.fields:
                if fld.name not in names:
                    names.append(fld.name)
        return cls(
            filename=filename,
            entities=[e.name for e in program.entities],
            field_names=names,
            relationship_count=len(program.relationships),
            **kwargs,
        )


@dataclass
class EntityVerification:
    """Post-publish presence check for one declared entity (REQ-291).

    :ivar entity: The entity's natural (YAML) name.
    :ivar present: Whether the entity was found on the live target after the
        publish (``None`` when the check was inconclusive — e.g. the target's
        scopes could not be read).
    :ivar fields_present: Declared field names confirmed present on the target.
    :ivar fields_missing: Declared field names not found on the target.
    :ivar status: ``matching`` | ``partial`` | ``missing`` | ``unverified``.
    """

    entity: str
    present: bool | None
    fields_present: list[str] = field(default_factory=list)
    fields_missing: list[str] = field(default_factory=list)
    status: str = "unverified"


@dataclass
class VerificationResult:
    """The outcome of re-reading the target after a publish (REQ-291).

    :ivar ran: Whether a verification pass was attempted (False for preview /
        validate-only runs).
    :ivar conclusive: Whether the target's live state could actually be read;
        False means the result is advisory only (e.g. scopes unreadable).
    :ivar all_present: True when every declared entity + field was confirmed.
    :ivar entities: Per-entity verification detail.
    :ivar warnings: Best-effort read warnings (unreachable entity, etc.).
    """

    ran: bool = False
    conclusive: bool = True
    all_present: bool = False
    entities: list[EntityVerification] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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
    :ivar verification: The post-publish target verification (REQ-291), or
        ``None`` when no real publish ran (preview / validate-only).
    :ivar backup: The pre-publish snapshot of the target captured before deploy
        (REQ-292), or ``None`` (preview / validate-only, or capture skipped).
    :ivar aborted: True when the publish was abandoned before deploying because
        the pre-publish backup could not be captured and was not overridden.
    :ivar abort_reason: Why the publish aborted, when ``aborted``.
    :ivar settings: The governed-settings apply outcome (PI-406 / REQ-485), or
        ``None`` when the instance has no declared per-instance values.
    :ivar settings_log: The governed-settings apply log lines, when captured.
    """

    engine: str
    target_instance: str
    validate_only: bool
    validation_failed: bool
    preview: bool = False
    programs: list[ProgramOutcome] = field(default_factory=list)
    deferrals: list = field(default_factory=list)
    #: REQ-489 / DEC-921 — design facts captured but deliberately not applied
    #: (saved views; workflows per DEC-997). Informational; never an action.
    captured_only: list = field(default_factory=list)
    manual_config: str | None = None
    verification: VerificationResult | None = None
    backup: dict | None = None
    aborted: bool = False
    settings: SettingsResult | None = None
    settings_log: list = field(default_factory=list)
    #: REQ-496 / PI-411 — the identity of this run's derived plan; a preview
    #: hands it to the operator, the apply proves it against a re-derivation.
    plan_fingerprint: str | None = None
    #: True when the apply refused because the re-derived plan no longer
    #: matched the one the operator was shown.
    plan_moved: bool = False
    #: REQ-495 — the design-version stamp write outcome, or ``None`` when the
    #: run did not qualify to write one (no frozen release named, preview, or
    #: any outcome short of full success).
    stamp: SettingsResult | None = None
    stamp_log: list = field(default_factory=list)
    #: REQ-497 / DEC-982 — the changes an automatic apply declined, each
    #: carrying its kind and reason. Non-empty only on a refused run.
    declined_changes: list = field(default_factory=list)
    abort_reason: str | None = None


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


def _declared_fields(
    programs: list[tuple[str, ProgramFile]]
) -> dict[str, list[str]]:
    """Map each declared entity natural name to the field names it declares.

    The union across all programs (a native entity is commonly extended by
    several domain YAMLs), de-duplicated, preserving first-seen order.
    """
    out: dict[str, list[str]] = {}
    for _, program in programs:
        for entity in program.entities:
            bucket = out.setdefault(entity.name, [])
            for fld in entity.fields:
                if fld.name not in bucket:
                    bucket.append(fld.name)
    return out


#: gather_server_fields emits this when the target's scopes can't be read,
#: which makes a presence check inconclusive rather than "everything missing".
_SCOPES_UNREADABLE = "Could not read live instance scopes"


def declared_setting_values(
    design_client: DesignClient, instance_identifier: str
) -> dict:
    """The governed key -> declared value mapping for one instance (REQ-485).

    Only *declared* rows contribute — a governed setting with no declared value
    for this instance is not captured, and the applier must not invent one.
    The mapping is keyed by ``system_setting_key`` (the name the CRM itself
    uses), so the applier and the ordinary-credential reader agree on names.
    """
    key_by_id = {
        s["system_setting_identifier"]: s["system_setting_key"]
        for s in design_client.list_system_settings()
        if s.get("system_setting_status") == "confirmed"
    }
    declared: dict = {}
    for row in design_client.list_system_setting_values(instance_identifier):
        key = key_by_id.get(row.get("system_setting_identifier"))
        if key is not None:
            declared[key] = row.get("value")
    return declared


def automatic_apply_declines(
    programs: list[tuple[str, ProgramFile]], client: EspoAdminClient
) -> list[dict]:
    """The changes an automatic apply of these programs must decline (REQ-497).

    A publish without an approved plan fingerprint is an automatic apply
    (DEC-982), and may only add or widen. This derives the plan's
    attribute-level changes against the live target — declared entity
    deletions, a declared type differing from the live one, and a declared
    option set missing values the live field permits — and screens them with
    the tested :func:`screen_automatic` fence. A field or entity the target
    does not carry is an addition and passes. A live read that fails is
    treated as the engine treats it: the objects deploy as new, which is
    additive.

    :returns: the declined changes, each carrying ``kind`` and ``reason``.
    """
    changes: list[dict] = []
    for filename, program in programs:
        for entity in program.entities:
            if entity.action in (
                EntityAction.DELETE, EntityAction.DELETE_AND_CREATE
            ):
                changes.append({
                    "construct": f"entity {entity.name} ({filename})",
                    "attribute": "entity",
                    "design": None,
                    "instance": entity.name,
                })
            status, defs = client.get_entity_field_list(
                get_espo_entity_name(entity.name)
            )
            if status != 200 or not isinstance(defs, dict):
                continue  # absent or unreadable: deploys as new — additive
            for fld in entity.fields:
                live = defs.get(fld.name) or defs.get(
                    "c" + fld.name[:1].upper() + fld.name[1:]
                )
                if not isinstance(live, dict):
                    continue  # new field: additive
                construct = f"field {entity.name}.{fld.name} ({filename})"
                live_type = live.get("type")
                if live_type and fld.type and live_type != fld.type:
                    changes.append({
                        "construct": construct,
                        "attribute": "field_type",
                        "design": fld.type,
                        "instance": live_type,
                    })
                declared_options = list(getattr(fld, "options", None) or [])
                live_options = live.get("options")
                if declared_options and isinstance(live_options, list):
                    changes.append({
                        "construct": construct,
                        "attribute": "field_options",
                        "design": declared_options,
                        "instance": live_options,
                    })
    _, declined = screen_automatic(changes)
    return declined


def plan_fingerprint_for(
    artifacts: list[tuple[str, str]],
    *,
    target_identifier: str,
    setting_values: dict,
) -> str:
    """The identity of the plan a publish would apply (REQ-496 / PI-411).

    Covers everything that determines *what gets written, and where*: the
    scoped program contents keyed by generated filename, the target instance,
    and the declared per-instance setting values the same run would write
    (PI-406) — a governed value changed between showing the plan and applying
    it moves the identity exactly as a program change does, and a fingerprint
    approved for one instance approves nothing on another. The provenance
    comment header is excluded — it carries ``rendered_at``, so two
    derivations of the same design at different moments must still fingerprint
    identically, while any change to what would be written changes the result.
    """
    def _body(content: str) -> str:
        lines = content.split("\n")
        i = 0
        while i < len(lines) and lines[i].startswith("#"):
            i += 1
        return "\n".join(lines[i:])

    return fingerprint_plan(
        {
            "target_instance": target_identifier,
            "programs": {fn: _body(c) for fn, c in artifacts},
            "setting_values": setting_values,
        }
    )


def verify_publish(
    programs: list[tuple[str, ProgramFile]],
    server_fields: dict[str, frozenset[str]],
    warnings: list[str],
) -> VerificationResult:
    """Confirm the declared entities + fields are present on the target.

    Pure comparison of what was published (the parsed programs) against the
    target's post-publish live field state (``server_fields`` from a re-read
    via :func:`gather_server_fields`). This is the REQ-291 post-publish gate:
    it answers "did the publish actually land?" per object.

    :param programs: the ``(filename, ProgramFile)`` pairs that were deployed.
    :param server_fields: ``{entity_natural_name: frozenset(field_names)}`` read
        back from the live target after the deploy.
    :param warnings: best-effort read warnings from the re-read.
    :returns: a :class:`VerificationResult`.
    """
    conclusive = not any(_SCOPES_UNREADABLE in w for w in warnings)
    declared = _declared_fields(programs)
    entities: list[EntityVerification] = []
    all_present = True

    for entity in sorted(declared):
        want = declared[entity]
        if not conclusive:
            entities.append(
                EntityVerification(entity=entity, present=None, status="unverified")
            )
            all_present = False
            continue
        live = server_fields.get(entity)
        if live is None:
            # Entity not present on the target after publish.
            entities.append(
                EntityVerification(
                    entity=entity,
                    present=False,
                    fields_missing=list(want),
                    status="missing",
                )
            )
            all_present = False
            continue
        present_fields = [f for f in want if f in live]
        missing_fields = [f for f in want if f not in live]
        status = "matching" if not missing_fields else "partial"
        if missing_fields:
            all_present = False
        entities.append(
            EntityVerification(
                entity=entity,
                present=True,
                fields_present=present_fields,
                fields_missing=missing_fields,
                status=status,
            )
        )

    return VerificationResult(
        ran=True,
        conclusive=conclusive,
        all_present=conclusive and all_present,
        entities=entities,
        warnings=list(warnings),
    )


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
    scope: set[str] | None = None,
    allow_no_backup: bool = False,
    expected_plan_fingerprint: str | None = None,
    release_identifier: str | None = None,
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
    :param scope: If given, publish only the programs whose generated filename
        is in this set — a subset publish (REQ-290). ``None`` or empty means
        publish everything (the default). Validation, preview, verification,
        and the manual-config checklist all operate over the scoped subset.
    :param allow_no_backup: If True, proceed with the publish even when the
        pre-publish backup cannot be captured (REQ-292 gate override). Default
        False: a failed backup aborts the publish before any write.
    :param expected_plan_fingerprint: The plan identity the operator was shown
        (from a preview). On a real publish, the plan is re-derived and a
        mismatch refuses the apply, reporting the newly derived plan
        (REQ-496 / PI-411). ``None`` skips the gate.
    :param release_identifier: The frozen release this publish runs under.
        When given, a run whose terminal status is ``succeeded`` writes the
        design-version stamp into the instance (REQ-495 / DEC-980, DEC-981);
        a publish outside a frozen release never writes it. The caller
        validates the release's freeze state.
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
    # Scoped publish (REQ-290): keep only the selected programs. An empty/None
    # scope publishes everything.
    if scope:
        programs = [(f, p) for f, p in programs if f in scope]
    scoped_artifacts = [
        (a.filename, a.content)
        for a in result.programs
        if not scope or a.filename in scope
    ]

    # Read the declared per-instance values once, before the fingerprint is
    # derived, so the values the plan identity covers are exactly the values
    # a successful run would write (REQ-496 / REQ-485).
    declared = declared_setting_values(design_client, target_identifier)

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
        plan_fingerprint=plan_fingerprint_for(
            scoped_artifacts,
            target_identifier=target_identifier,
            setting_values=declared,
        ),
        deferrals=list(result.deferrals),
        captured_only=list(result.captured_only),
        manual_config=(
            result.manual_config.content if result.manual_config else None
        ),
    )

    # Validation gate: never touch a program that does not pass its own engine
    # pre-flight (REQ-288). A validate-only run stops here too.
    if validate_only or validation_failed:
        for filename, program in programs:
            pub.programs.append(
                ProgramOutcome.for_program(
                    filename,
                    program,
                    validation_errors=failures.get(filename, []),
                    deployed=False,
                )
            )
        return pub

    # Plan-identity gate (REQ-496 / PI-411): the plan was re-derived by the
    # generation above; if the operator approved a different plan, refuse and
    # report the newly derived one rather than proceeding. A preview writes
    # nothing and is how the fingerprint is obtained, so it is never gated.
    if (
        not preview
        and expected_plan_fingerprint is not None
        and expected_plan_fingerprint != pub.plan_fingerprint
    ):
        pub.aborted = True
        pub.plan_moved = True
        pub.abort_reason = (
            "the plan has moved since it was shown: the design now derives "
            f"plan {pub.plan_fingerprint}, not the approved "
            f"{expected_plan_fingerprint}. Nothing was applied; review the "
            "newly derived plan and approve it."
        )
        for filename, program in programs:
            pub.programs.append(
                ProgramOutcome.for_program(filename, program, deployed=False)
            )
        return pub

    # Additive-only fence (REQ-497 / DEC-982): a publish without an approved
    # plan fingerprint is an automatic apply and may only add or widen. A
    # removal, narrowing, or type change is refused by name; the reviewed run
    # that may carry them is the preview-then-approve flow above.
    if not preview and expected_plan_fingerprint is None:
        declined = automatic_apply_declines(programs, client)
        if declined:
            pub.aborted = True
            pub.declined_changes = declined
            named = "; ".join(
                f"{d.get('construct')}: {d['kind']} — {d['reason']}"
                for d in declined
            )
            pub.abort_reason = (
                "an automatic apply may only add or widen (REQ-497); "
                f"declined {len(declined)} change(s): {named}. Nothing was "
                "applied. Run a publish preview, review these changes, and "
                "resubmit with the approved plan fingerprint."
            )
            for filename, program in programs:
                pub.programs.append(
                    ProgramOutcome.for_program(
                        filename, program, deployed=False
                    )
                )
            return pub

    # Backup gate (REQ-292): for a real publish, capture a pre-publish snapshot
    # of the target before writing anything. A total capture failure aborts the
    # publish unless explicitly overridden. A preview writes nothing, so it
    # needs no backup.
    if not preview:
        try:
            pub.backup = capture_target_backup(client, _entity_names(programs))
        except BackupCaptureError as exc:
            if not allow_no_backup:
                pub.aborted = True
                pub.abort_reason = str(exc)
                for filename, program in programs:
                    pub.programs.append(
                        ProgramOutcome.for_program(
                            filename, program, deployed=False
                        )
                    )
                return pub
            # Overridden: proceed with no backup recorded.
            pub.backup = None

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
            ProgramOutcome.for_program(
                filename,
                program,
                validation_errors=[],
                deployed=not preview,
                report=outcome.report,
                log=log,
            )
        )

    # Governed per-instance setting values (PI-406 / REQ-485): instance-level,
    # not per-program, and independent of the entity feature selection. A
    # preview dry-runs the write exactly as the deploy engine above does.
    # (``declared`` was read once, above, inside the plan fingerprint.)
    if declared:
        settings_log: list[tuple[str, str]] = []
        settings_ofn: OutputFn = output_fn or (
            lambda m, c, _log=settings_log: _log.append((m, c))
        )
        settings_mgr = SystemSettingsManager(client, settings_ofn)
        try:
            pub.settings = settings_mgr.apply_values(declared, dry_run=preview)
        except SystemSettingsManagerError as exc:
            pub.settings = SettingsResult(
                entity="CNetworkStandard",
                status=SettingsStatus.ERROR,
                error=str(exc),
            )
        pub.settings_log = settings_log

    # Post-publish verify (REQ-291): re-read the live target and confirm the
    # declared entities + fields landed. Only for a real publish — a preview
    # writes nothing, so there is nothing to verify.
    if not preview:
        post_fields, post_warnings = gather_server_fields(
            client, _entity_names(programs)
        )
        pub.verification = verify_publish(programs, post_fields, post_warnings)

    # Design-version stamp (REQ-495 / DEC-980, DEC-981): written only by a
    # run under a frozen release whose terminal status is succeeded — a
    # partial failure, an unverified result (succeeded_with_issues), or an
    # ordinary publish outside a release leaves the previous stamp untouched.
    if (
        release_identifier is not None
        and not preview
        and publish_run_status(pub) == "succeeded"
    ):
        stamp_log: list[tuple[str, str]] = []
        stamp_ofn: OutputFn = output_fn or (
            lambda m, c, _log=stamp_log: _log.append((m, c))
        )
        stamp_mgr = SystemSettingsManager(client, stamp_ofn)
        try:
            pub.stamp = stamp_mgr.write_stamp(
                standard_version=release_identifier,
                plan_fingerprint=pub.plan_fingerprint or "",
            )
        except SystemSettingsManagerError as exc:
            pub.stamp = SettingsResult(
                entity="CNetworkStandard",
                status=SettingsStatus.ERROR,
                error=str(exc),
            )
        pub.stamp_log = stamp_log

    return pub


def publish_run_status(result: PublishResult) -> str:
    """Map a publish result to a terminal ``publish_run`` status (REQ-293).

    Shared with the API router (which records the run) and the stamp gate
    in :func:`publish` (DEC-981: only ``succeeded`` writes the stamp).
    """
    if result.aborted:
        return "aborted"
    if result.validation_failed or any(
        not p.deployed for p in result.programs
    ):
        return "failed"
    # A governed-settings write failure is a publish failure (PI-406 /
    # REQ-485); a NOT_SUPPORTED carrier stays a manual-config outcome.
    if (
        result.settings is not None
        and result.settings.status is SettingsStatus.ERROR
    ):
        return "failed"
    verify = result.verification
    if verify is not None and verify.ran and verify.conclusive and not (
        verify.all_present
    ):
        return "succeeded_with_issues"
    return "succeeded"
