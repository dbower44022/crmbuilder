"""Publishing a design to a live CRM system (REQ-287, REQ-288, REQ-618).

Four steps, all of them version 2's own since PI-532:

1. **Generate** the declaration from the canonical design, in memory.
2. **Read it back**, so what is applied is provably the file a person can
   read. The emitter and the parser are held together by a test rather than
   by hope.
3. **Check** each declaration against the others and against the live target,
   because a declaration may legitimately name a field another file declares
   or one the instance already has.
4. **Apply** it through the version 2 appliers, in an order that works, with
   every fence this module holds: the plan the operator approved has not
   moved, access is not taken away without a word, and a backup was captured.

A run that only validates stops after step 3. Nothing here needs a graphical
toolkit, and only :func:`publish` touches a real instance — everything else
is exercised with fakes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from crmbuilder_v2.access.apply_plan import (
    REMOVAL,
    fingerprint_plan,
    screen_automatic,
)
from crmbuilder_v2.adapters.base import GenerationResult
from crmbuilder_v2.adapters.espocrm.adapter import EspoCrmAdapter
from crmbuilder_v2.adapters.espocrm.client import DesignClient
from crmbuilder_v2.introspect.espo_client import EspoConnectionConfig
from crmbuilder_v2.introspect.utilization import wire_entity_name
from crmbuilder_v2.publish import governed_settings
from crmbuilder_v2.publish import run as run_engine
from crmbuilder_v2.publish.access import assess_publish_access, describe_removals
from crmbuilder_v2.publish.backup import BackupCaptureError, capture_target_backup
from crmbuilder_v2.publish.declaration import (
    Declaration,
    DeclarationError,
    validate_batch,
)
from crmbuilder_v2.publish.declaration import parse as parse_declaration
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient
from crmbuilder_v2.publish.from_declaration import plan_for
from crmbuilder_v2.publish.live_state import gather_server_fields

OutputFn = Callable[[str, str], None]


@dataclass
class ProgramOutcome:
    """The result of validating (and optionally deploying) one program file.

    :ivar filename: The generated program filename, e.g. ``Contact.yaml``.
    :ivar validation_errors: Validator errors; empty means the program is valid.
    :ivar deployed: Whether this program was applied to the target.
    :ivar report: The :class:`~crmbuilder_v2.publish.run.RunReport` for this
        program, or ``None`` if it was not applied.
    :ivar log: Captured ``(message, color)`` deploy log lines.
    :ivar entities: Natural entity names this program declares.
    :ivar field_names: Field names this program declares, across its entities,
        de-duplicated in first-seen order.
    :ivar relationship_count: Link relationships this program declares.
    """

    filename: str
    validation_errors: list[str] = field(default_factory=list)
    deployed: bool = False
    report: run_engine.RunReport | None = None
    log: list[tuple[str, str]] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    field_names: list[str] = field(default_factory=list)
    relationship_count: int = 0

    @classmethod
    def for_program(
        cls, filename: str, program: Declaration, **kwargs
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
        for declared in program.field_names().values():
            for name in sorted(declared):
                if name not in names:
                    names.append(name)
        return cls(
            filename=filename,
            entities=[str(name) for name in program.entities],
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
    #: What the platform will not do, gathered from every applied program —
    #: the list a person works through by hand after a publish.
    manual_config_items: list[str] = field(default_factory=list)
    verification: VerificationResult | None = None
    backup: dict | None = None
    aborted: bool = False
    settings: governed_settings.SettingsOutcome | None = None
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
    stamp: governed_settings.SettingsOutcome | None = None
    stamp_log: list = field(default_factory=list)
    #: REQ-497 / DEC-982 — the changes an automatic apply will not make, each
    #: carrying its kind and reason. A refused run reports what it declined; a
    #: preview reports the same list in advance, so an operator reads it
    #: before running the apply rather than after it refuses.
    declined_changes: list = field(default_factory=list)
    #: REQ-521 / PI-466 — what this publish does to access on the target:
    #: each declared role and team against the target's live roles, in the
    #: reconcile route's words, or ``known: False`` when the target could not
    #: be read. ``None`` when the run stopped before the assessment
    #: (validate-only, validation failure).
    access: dict | None = None
    #: True when a reviewed run was refused because it takes access away and
    #: the request did not carry the separate removal confirmation.
    access_removal_unconfirmed: bool = False
    abort_reason: str | None = None


def build_target_profile(
    instance_record: dict,
    *,
    api_key: str,
    secret_key: str | None = None,
) -> EspoConnectionConfig:
    """How to reach the target, from its record and its resolved secrets.

    The same mapping the audit uses, so a publish describes its target the
    way the audit describes its source.

    :param instance_record: The target's record.
    :param api_key: The resolved key or password.
    :param secret_key: The resolved secret, where the authentication method
        uses one.
    """
    return EspoConnectionConfig(
        base_url=instance_record["instance_url"],
        api_key=api_key,
        secret_key=secret_key,
        auth_method=instance_record.get("instance_auth_method") or "api_key",
    )


def generate_design_yaml(
    design_client: DesignClient,
    *,
    rendered_at: str,
    engagement: str | None = None,
) -> GenerationResult:
    """Fetch the canonical design and generate engine YAML in memory.

    Replicates the adapter's fetch→generate steps without writing files: every
    design list the adapter's own ``run`` reads is read from ``design_client``
    and handed to :meth:`EspoCrmAdapter.generate`.

    The two lists must stay in step. Until PI-417 this read nine lists while
    ``run`` read eleven, so a publish never rendered the field-permission and
    field-visibility blocks — and would never have rendered the security
    program either, leaving a role publish scoped to a file that did not exist.

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
        field_permission_rules=design_client.list_field_permission_rules(),
        field_visibility_rules=design_client.list_field_visibility_rules(),
        roles=design_client.list_roles(),
        teams=design_client.list_teams(),
        filtered_tabs=design_client.list_filtered_tabs(),
        layouts=design_client.list_layouts(),
        rendered_at=rendered_at,
        engagement=engagement,
    )


def parse_programs(
    result: GenerationResult,
) -> list[tuple[str, Declaration]]:
    """Read each generated program back as a declaration.

    The publish path emits the declaration and then reads it again, so what
    is applied is provably the file a person can read. A program that cannot
    be read at all is carried as a declaration with no content and fails
    validation by name, rather than raising and taking the run with it.

    :param result: The adapter generation result.
    :returns: ``(filename, Declaration)`` pairs in generation order.
    """
    parsed: list[tuple[str, Declaration]] = []
    for artifact in result.programs:
        try:
            parsed.append(
                (artifact.filename, parse_declaration(artifact.content, artifact.filename))
            )
        except DeclarationError as exc:
            parsed.append(
                (artifact.filename, Declaration(artifact.filename, {"__unreadable__": str(exc)}))
            )
    return parsed


def companion_files(result: GenerationResult) -> dict[str, str]:
    """The files written beside the declarations, by name.

    A message template's body is one of these: the emitter keeps it out of
    the declaration so a long block of markup does not drown everything else
    in the file.
    """
    return {a.filename: a.content for a in result.companions}


def validate_programs(
    programs: list[tuple[str, Declaration]],
    server_fields_by_entity: dict[str, frozenset[str]] | None = None,
) -> dict[str, list[str]]:
    """Check every generated program, against each other and the target.

    A declaration may name a field another declaration declares, or one the
    instance already has, so the check is made against the batch and the
    target together rather than file by file.

    :param programs: ``(filename, Declaration)`` pairs.
    :param server_fields_by_entity: The fields already on the target, by
        object type, or ``None`` to check the batch alone.
    :returns: ``{filename: [problems]}`` for any program with problems.
    """
    unreadable = {
        filename: [str(declaration.content["__unreadable__"])]
        for filename, declaration in programs
        if "__unreadable__" in declaration.content
    }
    readable = [
        declaration
        for _, declaration in programs
        if "__unreadable__" not in declaration.content
    ]
    return {**validate_batch(readable, server_fields_by_entity), **unreadable}


def _entity_names(programs: list[tuple[str, Declaration]]) -> list[str]:
    """Every object type the programs name, in the order they name it."""
    names: list[str] = []
    for _, declaration in programs:
        for name in declaration.entities:
            if str(name) not in names:
                names.append(str(name))
    return names


def _declared_fields(
    programs: list[tuple[str, Declaration]]
) -> dict[str, list[str]]:
    """Map each declared entity natural name to the field names it declares.

    The union across all programs (a native entity is commonly extended by
    several domain YAMLs), de-duplicated, preserving first-seen order.
    """
    out: dict[str, list[str]] = {}
    for _, declaration in programs:
        for entity, names in declaration.field_names().items():
            bucket = out.setdefault(entity, [])
            for name in sorted(names):
                if name not in bucket:
                    bucket.append(name)
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
    programs: list[tuple[str, Declaration]],
    client: EspoWriteClient,
    *,
    access: dict | None = None,
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

    Access is screened from the assessment already made (REQ-521 / PI-466):
    every setting the security program would lower — a scope level, a system
    permission — is a removal, declined by name. The judgement of what counts
    as lowering is the reconcile gate's, not restated here.

    :param access: the :func:`assess_publish_access` section for this run,
        or ``None`` to screen the programs alone.
    :returns: the declined changes, each carrying ``kind`` and ``reason``.
    """
    changes: list[dict] = []
    for filename, declaration in programs:
        for entity_name, block in declaration.entities.items():
            if not isinstance(block, dict):
                continue
            entity = str(entity_name)
            if str(block.get("action") or "").lower() in (
                "delete",
                "delete_and_create",
            ):
                changes.append({
                    "construct": f"entity {entity} ({filename})",
                    "attribute": "entity",
                    "design": None,
                    "instance": entity,
                })
            status, defs = client.get_entity_field_list(wire_entity_name(entity))
            if status != 200 or not isinstance(defs, dict):
                continue  # absent or unreadable: deploys as new — additive
            for declared in block.get("fields") or []:
                if not isinstance(declared, dict) or not declared.get("name"):
                    continue
                name = str(declared["name"])
                live = defs.get(name) or defs.get(
                    "c" + name[:1].upper() + name[1:]
                )
                if not isinstance(live, dict):
                    continue  # new field: additive
                construct = f"field {entity}.{name} ({filename})"
                live_type = live.get("type")
                declared_type = declared.get("type")
                if live_type and declared_type and live_type != declared_type:
                    changes.append({
                        "construct": construct,
                        "attribute": "field_type",
                        "design": declared_type,
                        "instance": live_type,
                    })
                declared_options = list(declared.get("options") or [])
                live_options = live.get("options")
                if declared_options and isinstance(live_options, list):
                    changes.append({
                        "construct": construct,
                        "attribute": "field_options",
                        "design": declared_options,
                        "instance": live_options,
                    })
    _, declined = screen_automatic(changes)
    for removal in (access or {}).get("removals", []):
        declined.append({
            "construct": f"role {removal.get('member_name')} (security.yaml)",
            "attribute": removal.get("attribute"),
            "design": removal.get("after"),
            "instance": removal.get("before"),
            "kind": REMOVAL,
            "reason": (
                "takes away access the instance currently grants: "
                f"{removal.get('description')}"
            ),
        })
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
    programs: list[tuple[str, Declaration]],
    server_fields: dict[str, frozenset[str]],
    warnings: list[str],
) -> VerificationResult:
    """Confirm the declared entities + fields are present on the target.

    Pure comparison of what was published (the parsed declarations) against the
    target's post-publish live field state (``server_fields`` from a re-read
    via :func:`gather_server_fields`). This is the REQ-291 post-publish gate:
    it answers "did the publish actually land?" per object.

    :param programs: the ``(filename, Declaration)`` pairs that were applied.
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
    confirm_access_removal: bool = False,
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
    :param confirm_access_removal: The operator's separate word that access
        the target currently grants may be taken away (REQ-521 / PI-466).
        Without it a reviewed run carrying a removal is refused
        (``access_removal_unconfirmed``) and an automatic run declines the
        removal (DEC-982); with it, the removal — or an effect the target
        would not let us read — proceeds. The reconcile route's gate collects
        this word before calling; the whole-design route accepts it only
        alongside an approved plan fingerprint.
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
    client = EspoWriteClient(config=profile)

    result = generate_design_yaml(
        design_client, rendered_at=rendered_at, engagement=engagement
    )
    programs = parse_programs(result)
    companions = companion_files(result)
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

    # Access effect (REQ-521 / PI-466): what the security program in this
    # run would do to who can reach what, read from the target's live roles.
    # Stated on every preview and real run; the fences below act on it.
    pub.access = assess_publish_access(
        programs, design_client, client, target_identifier=target_identifier
    )

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

    # Removal fence on a reviewed run (REQ-521 / PI-466): approving the plan
    # is agreeing to push the roles, not to revoke what the instance grants.
    # A removal needs its own word, exactly as on the reconcile route.
    if (
        not preview
        and expected_plan_fingerprint is not None
        and pub.access["removes_access"]
        and not confirm_access_removal
    ):
        pub.aborted = True
        pub.access_removal_unconfirmed = True
        pub.abort_reason = (
            f"{pub.access['summary']} This publish removes access the "
            "instance currently grants and is never applied automatically; "
            "confirm the removal separately (confirm_access_removal): "
            + describe_removals(pub.access)
        )
        for filename, program in programs:
            pub.programs.append(
                ProgramOutcome.for_program(filename, program, deployed=False)
            )
        return pub

    # Additive-only fence (REQ-497 / DEC-982): a publish without an approved
    # plan fingerprint is an automatic apply and may only add or widen. A
    # removal, narrowing, or type change is refused by name; the reviewed run
    # that may carry them is the preview-then-approve flow above. Access the
    # security program would lower is a removal (PI-466), and an effect the
    # target would not let us read is not proven additive, so it is refused
    # too — unless the removal was confirmed in so many words.
    # A preview answers "what would happen", and what would happen includes
    # what an automatic apply would refuse. Reporting it only on the apply —
    # after an operator has read a clean-looking preview — is how a publish
    # surprises somebody (CBMTEST, 2026-09-19: a preview reporting four
    # unchanged fields, an apply refusing all four).
    if preview and expected_plan_fingerprint is None:
        pub.declined_changes = automatic_apply_declines(
            programs,
            client,
            access=None if confirm_access_removal else pub.access,
        )

    if not preview and expected_plan_fingerprint is None:
        access_unknown = (
            pub.access["assessed"]
            and not pub.access["known"]
            and not confirm_access_removal
        )
        if access_unknown:
            pub.aborted = True
            pub.abort_reason = (
                f"{pub.access['summary']}. An automatic apply proceeds only "
                "when it is proven to add or widen (DEC-982), and the "
                "security program's effect on access is unknown. Nothing "
                "was applied. Run a publish preview when the target can be "
                "read, review the access effect, and resubmit with the "
                "approved plan fingerprint."
            )
            for filename, program in programs:
                pub.programs.append(
                    ProgramOutcome.for_program(
                        filename, program, deployed=False
                    )
                )
            return pub
        declined = automatic_apply_declines(
            programs,
            client,
            access=None if confirm_access_removal else pub.access,
        )
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

    # Apply each program, or — on a preview — report what it would do without
    # writing anything (REQ-289). One program at a time, because a person
    # reads the result per file and a failure in one must not stop the rest.
    for filename, declaration in programs:
        log: list[tuple[str, str]] = []
        ofn: OutputFn = output_fn or (
            lambda m, c, _log=log: _log.append((m, c))
        )
        report = run_engine.apply_plan(
            client,
            plan_for([declaration], companions=companions),
            preview=preview,
        )
        for line in run_engine.describe(report):
            ofn(line, "gray")
        pub.programs.append(
            ProgramOutcome.for_program(
                filename,
                declaration,
                validation_errors=[],
                deployed=not preview and report.succeeded,
                report=report,
                log=log,
            )
        )
        pub.manual_config_items.extend(report.manual_config)

    # Governed per-instance setting values (PI-406 / REQ-485): instance-level,
    # not per-program, and independent of the entity feature selection. A
    # preview dry-runs the write exactly as the deploy engine above does.
    # (``declared`` was read once, above, inside the plan fingerprint.)
    if declared:
        settings_log: list[tuple[str, str]] = []
        settings_ofn: OutputFn = output_fn or (
            lambda m, c, _log=settings_log: _log.append((m, c))
        )
        pub.settings = governed_settings.apply_values(
            client, declared, preview=preview
        )
        if pub.settings.detail:
            settings_ofn(pub.settings.detail, "gray")
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
        pub.stamp = governed_settings.write_stamp(
            client,
            design_version=release_identifier,
            plan=pub.plan_fingerprint or "",
        )
        if pub.stamp.detail:
            stamp_ofn(pub.stamp.detail, "gray")
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
        and result.settings.failed
    ):
        return "failed"
    verify = result.verification
    if verify is not None and verify.ran and verify.conclusive and not (
        verify.all_present
    ):
        return "succeeded_with_issues"
    return "succeeded"
