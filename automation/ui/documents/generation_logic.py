"""Pure-Python state machine for document generation progress (Section 14.7.4).

Tracks the six stages of the generation pipeline for inline progress display.
No PySide6 imports.
"""

from __future__ import annotations

import dataclasses
import enum


class GenerationStage(enum.Enum):
    """Six stages of the generation pipeline."""

    QUERY = "query"
    VALIDATE = "validate"
    RENDER = "render"
    WRITE = "write"
    GIT_COMMIT = "git_commit"
    GENERATION_LOG = "generation_log"


STAGE_ORDER = list(GenerationStage)

STAGE_LABELS: dict[GenerationStage, str] = {
    GenerationStage.QUERY: "Query",
    GenerationStage.VALIDATE: "Validate",
    GenerationStage.RENDER: "Render",
    GenerationStage.WRITE: "Write",
    GenerationStage.GIT_COMMIT: "Git Commit",
    GenerationStage.GENERATION_LOG: "Generation Log",
}

# Stages that only apply to final mode
FINAL_ONLY_STAGES = {GenerationStage.GIT_COMMIT, GenerationStage.GENERATION_LOG}


class GenerationState(enum.Enum):
    """Overall generation state."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED_WARNINGS = "paused_warnings"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclasses.dataclass
class GenerationProgress:
    """Tracks progress through the generation pipeline.

    :param mode: 'final' or 'draft'.
    """

    mode: str = "final"
    state: GenerationState = GenerationState.IDLE
    current_stage: GenerationStage | None = None
    completed_stages: list[GenerationStage] = dataclasses.field(default_factory=list)
    warnings: list[str] = dataclasses.field(default_factory=list)
    error: str | None = None
    # Result data
    file_path: str | None = None
    git_commit_hash: str | None = None

    @property
    def applicable_stages(self) -> list[GenerationStage]:
        """Return stages applicable to the current mode."""
        if self.mode == "draft":
            return [s for s in STAGE_ORDER if s not in FINAL_ONLY_STAGES]
        return list(STAGE_ORDER)

    @property
    def is_done(self) -> bool:
        """Whether the generation has reached a terminal state."""
        return self.state in (
            GenerationState.COMPLETED,
            GenerationState.FAILED,
            GenerationState.CANCELLED,
        )


def start_generation(mode: str = "final") -> GenerationProgress:
    """Create a new generation progress in the RUNNING state.

    :param mode: 'final' or 'draft'.
    :returns: A fresh GenerationProgress.
    """
    progress = GenerationProgress(mode=mode)
    progress.state = GenerationState.RUNNING
    stages = progress.applicable_stages
    if stages:
        progress.current_stage = stages[0]
    return progress


def advance_stage(progress: GenerationProgress) -> GenerationProgress:
    """Move to the next stage.

    :param progress: Current progress.
    :returns: Updated progress (same object, mutated).
    """
    if progress.state != GenerationState.RUNNING or progress.current_stage is None:
        return progress

    progress.completed_stages.append(progress.current_stage)
    stages = progress.applicable_stages
    current_idx = stages.index(progress.current_stage)

    if current_idx + 1 < len(stages):
        progress.current_stage = stages[current_idx + 1]
    else:
        progress.current_stage = None
        progress.state = GenerationState.COMPLETED

    return progress


def pause_for_warnings(
    progress: GenerationProgress, warnings: list[str]
) -> GenerationProgress:
    """Pause at the validate stage for warning review.

    :param progress: Current progress.
    :param warnings: List of warning messages.
    :returns: Updated progress.
    """
    progress.state = GenerationState.PAUSED_WARNINGS
    progress.warnings = warnings
    return progress


def resume_after_warnings(progress: GenerationProgress) -> GenerationProgress:
    """Resume generation after warnings are accepted.

    :param progress: Current progress (must be PAUSED_WARNINGS).
    :returns: Updated progress.
    """
    if progress.state != GenerationState.PAUSED_WARNINGS:
        return progress
    progress.state = GenerationState.RUNNING
    return advance_stage(progress)


def cancel_generation(progress: GenerationProgress) -> GenerationProgress:
    """Cancel the generation.

    :param progress: Current progress.
    :returns: Updated progress.
    """
    progress.state = GenerationState.CANCELLED
    return progress


def fail_generation(
    progress: GenerationProgress, error: str
) -> GenerationProgress:
    """Mark generation as failed.

    :param progress: Current progress.
    :param error: Error message.
    :returns: Updated progress.
    """
    progress.state = GenerationState.FAILED
    progress.error = error
    return progress


def set_result(
    progress: GenerationProgress,
    file_path: str | None = None,
    git_commit_hash: str | None = None,
) -> GenerationProgress:
    """Set result data on a completed generation.

    :param progress: Current progress.
    :param file_path: Output file path.
    :param git_commit_hash: Git commit hash (final mode only).
    :returns: Updated progress.
    """
    progress.file_path = file_path
    progress.git_commit_hash = git_commit_hash
    return progress


@dataclasses.dataclass
class BatchProgress:
    """Tracks progress through a batch generation.

    :param work_item_ids: The work item IDs to generate.
    """

    work_item_ids: list[int] = dataclasses.field(default_factory=list)
    current_index: int = 0
    current_name: str = ""
    success_count: int = 0
    skipped_count: int = 0
    failure_count: int = 0
    completed: bool = False

    @property
    def total(self) -> int:
        """Total number of documents in the batch."""
        return len(self.work_item_ids)

    @property
    def is_done(self) -> bool:
        """Whether the batch is complete."""
        return self.completed or self.current_index >= self.total


def start_batch(work_item_ids: list[int]) -> BatchProgress:
    """Create a new batch progress.

    :param work_item_ids: The work items to generate.
    :returns: A fresh BatchProgress.
    """
    return BatchProgress(work_item_ids=list(work_item_ids))


def record_batch_result(
    batch: BatchProgress, success: bool, skipped: bool = False
) -> BatchProgress:
    """Record the result of one document in the batch.

    :param batch: Current batch progress.
    :param success: Whether generation succeeded.
    :param skipped: Whether the document was skipped (e.g., warnings declined).
    :returns: Updated batch progress.
    """
    if skipped:
        batch.skipped_count += 1
    elif success:
        batch.success_count += 1
    else:
        batch.failure_count += 1

    batch.current_index += 1
    if batch.current_index >= batch.total:
        batch.completed = True
    return batch
