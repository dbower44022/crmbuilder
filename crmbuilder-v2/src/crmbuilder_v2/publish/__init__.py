"""PRJ-042 publish service — push the canonical V2 design to a target CRM.

The headless core that generates engine YAML from the canonical design,
validates it against the engine schema and the live target instance, and
deploys it through the shared :func:`espo_impl.core.deploy_pipeline.deploy_pipeline`.
"""

from crmbuilder_v2.publish.service import (
    ProgramOutcome,
    PublishResult,
    build_target_profile,
    generate_design_yaml,
    parse_programs,
    publish,
    validate_programs,
)

__all__ = [
    "ProgramOutcome",
    "PublishResult",
    "build_target_profile",
    "generate_design_yaml",
    "parse_programs",
    "publish",
    "validate_programs",
]
