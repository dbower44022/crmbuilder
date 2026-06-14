"""EspoCRM adapter — wires fetch → build → emit → self-check → write.

Implements the :class:`~crmbuilder_v2.adapters.base.CrmAdapter` contract
for ``engine == "espocrm"``. Responsibilities in order (design §10):
**derive** mechanics / **apply** defaults / **merge** overrides (in the
pure ``model.build_program_model``) → **emit** the artifact (``emit``) →
run the output through ``espo_impl.core.config_loader.validate_program``
as a self-check → **emit** the deferral companion → write atomically.

The CLI ``crmbuilder-v2-export-espocrm`` drives it against the live API.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from crmbuilder_v2.adapters.base import (
    CrmAdapter,
    Deferral,
    GenerationResult,
    ProgramArtifact,
)
from crmbuilder_v2.adapters.espocrm.client import DesignClient, RestDesignClient
from crmbuilder_v2.adapters.espocrm.emit import (
    MANUAL_CONFIG_FILENAME,
    emit_manual_config_md,
    emit_program_yaml,
)
from crmbuilder_v2.adapters.espocrm.model import build_program_model

ENGINE = "espocrm"


def validate_yaml_text(content: str) -> list[str]:
    """Run a generated YAML document through the deploy engine's
    ``validate_program`` and return its error list (empty == valid).

    The oracle (design §10 / REQ-143): the emitted artifact must pass the
    same validator the Configure flow runs as a hard-reject pre-flight.
    Imported lazily so the adapter package does not hard-depend on
    ``espo_impl`` at import time.
    """
    from espo_impl.core.config_loader import ConfigLoader

    loader = ConfigLoader()
    with tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        program = loader.load_program(tmp_path)
        return loader.validate_program(program)
    finally:
        tmp_path.unlink(missing_ok=True)


class EspoCrmAdapter(CrmAdapter):
    """The first engine backend (design §4): engine-neutral design records
    in, deployable EspoCRM YAML out."""

    engine = ENGINE

    def generate(
        self,
        entities: list[dict],
        fields: list[dict],
        overrides: list[dict],
        *,
        associations: list[dict] | None = None,
        rules: list[dict] | None = None,
        rendered_at: str,
        engagement: str | None = None,
    ) -> GenerationResult:
        """Pure generation: build the model and emit the artifact strings.

        No I/O and no validation here — :meth:`run` (or the caller) drives
        the self-check and the write. Deterministic for a fixed
        ``rendered_at``.
        """
        model = build_program_model(
            entities,
            fields,
            overrides,
            associations=associations,
            rules=rules,
            rendered_at=rendered_at,
            engagement=engagement,
        )
        programs = [
            ProgramArtifact(
                filename=p.filename,
                content=emit_program_yaml(p, rendered_at=rendered_at),
            )
            for p in model.programs
        ]
        manual = ProgramArtifact(
            filename=MANUAL_CONFIG_FILENAME,
            content=emit_manual_config_md(model, rendered_at=rendered_at),
        )
        return GenerationResult(
            engine=ENGINE,
            rendered_at=rendered_at,
            programs=programs,
            manual_config=manual,
            deferrals=list(model.deferrals),
        )

    def self_check(self, result: GenerationResult) -> dict[str, list[str]]:
        """Validate every generated program against ``validate_program``.

        Returns ``{filename: [errors]}`` for any program with errors
        (empty dict == all clean). The MANUAL-CONFIG companion is Markdown
        and is not validated.
        """
        failures: dict[str, list[str]] = {}
        for artifact in result.programs:
            errors = validate_yaml_text(artifact.content)
            if errors:
                failures[artifact.filename] = errors
        return failures

    def run(
        self,
        client: DesignClient,
        output_dir: Path,
        *,
        rendered_at: str,
        engagement: str | None = None,
    ) -> GenerationResult:
        """Fetch (impure) → generate (pure) → self-check → write.

        Raises ``RuntimeError`` (loud) if any generated program fails the
        validator — a deploy artifact that does not pass the engine's own
        pre-flight is never written as if it were good.
        """
        entities = client.list_entities()
        fields = client.list_fields()
        overrides = client.list_engine_overrides()
        associations = client.list_associations()
        rules = client.list_rules()
        result = self.generate(
            entities,
            fields,
            overrides,
            associations=associations,
            rules=rules,
            rendered_at=rendered_at,
            engagement=engagement,
        )
        failures = self.self_check(result)
        if failures:
            detail = "; ".join(
                f"{name}: {', '.join(errs)}" for name, errs in sorted(failures.items())
            )
            raise RuntimeError(
                f"generated EspoCRM YAML failed validate_program(): {detail}"
            )
        _write_artifacts(result, output_dir)
        return result


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via a same-directory temp + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _write_artifacts(result: GenerationResult, output_dir: Path) -> None:
    for artifact in result.programs:
        _atomic_write(output_dir / artifact.filename, artifact.content)
    if result.manual_config is not None:
        _atomic_write(
            output_dir / result.manual_config.filename,
            result.manual_config.content,
        )


def _deferral_summary(deferrals: list[Deferral]) -> str:
    by_kind: dict[str, int] = {}
    for d in deferrals:
        by_kind[d.kind] = by_kind.get(d.kind, 0) + 1
    return ", ".join(f"{k}: {n}" for k, n in sorted(by_kind.items())) or "none"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-export-espocrm",
        description=(
            "Generate deployable EspoCRM YAML program files from the "
            "engine-neutral V2 design records (PRJ-025 PI-191)."
        ),
    )
    parser.add_argument(
        "--engagement",
        required=True,
        help="engagement identifier or code (sent as the X-Engagement header)",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8765",
        help="V2 REST API base URL (default: http://127.0.0.1:8765)",
    )
    parser.add_argument(
        "--output",
        default=".",
        help="output directory for the generated YAML + MANUAL-CONFIG.md",
    )
    parser.add_argument(
        "--rendered-at",
        default=None,
        help="ISO timestamp for the provenance header (default: now, UTC)",
    )
    args = parser.parse_args(argv)

    rendered_at = args.rendered_at or datetime.now(UTC).isoformat()
    client = RestDesignClient(base_url=args.base_url, engagement=args.engagement)
    adapter = EspoCrmAdapter()
    output_dir = Path(args.output)
    try:
        result = adapter.run(
            client,
            output_dir,
            rendered_at=rendered_at,
            engagement=args.engagement,
        )
    except RuntimeError as exc:
        print(f"export failed: {exc}", file=sys.stderr)
        return 1

    # Section names, counts, and paths only — never a record value.
    print(f"engine: {result.engine}")
    print(f"engagement: {args.engagement}")
    print(f"output: {output_dir.resolve()}")
    print(f"programs: {len(result.programs)}")
    for artifact in result.programs:
        print(f"  - {artifact.filename}")
    print(f"manual-config: {MANUAL_CONFIG_FILENAME}")
    print(f"deferrals: {_deferral_summary(result.deferrals)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
