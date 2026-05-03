"""Tests for the Configure-tab validation wiring.

Covers the hard-reject behavior added in Prompt E of the
error-handling series. ``ConfigureProgressDialog._load_and_start``
must call ``ConfigLoader.validate_program`` after parsing each YAML
file. Files whose validation returns a non-empty error list are
excluded from the run, recorded in ``_file_results`` with a
``"Validation failed (N error(s))"`` outcome, and have their first
five errors mirrored into ``_file_tooltips``.

These tests construct the dialog under an offscreen ``QApplication``
and patch the network/DB seam (``load_instance_detail``) so no real
server contact is attempted. ``_run_next`` is monkey-patched so we can
assert whether it was invoked without launching a ``RunWorker``.
"""

from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

import pytest


@pytest.fixture(scope="module", autouse=True)
def _qapplication():
    """Boot an offscreen QApplication for dialog instantiation."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_yaml(tmp_path: Path, name: str, content: str):
    from automation.ui.deployment.deployment_logic import YamlFileInfo

    path = tmp_path / name
    path.write_text(dedent(content))
    return YamlFileInfo(
        name=name,
        path=str(path),
        last_modified="2026-05-03T00:00:00",
        last_run_outcome=None,
    )


_VALID_YAML = """\
    version: "1.0"
    description: "Valid program"
    entities:
      Contact:
        fields:
          - name: foo
            type: varchar
            label: "Foo"
"""

_INVALID_LINK_YAML = """\
    version: "1.0"
    description: "Invalid program with link field"
    entities:
      FUContribution:
        fields:
          - name: contributor
            type: link
            label: "Contributor"
"""


@pytest.fixture
def patched_dialog(monkeypatch):
    """Build a ConfigureProgressDialog with the network seams patched.

    Returns a factory ``(files) -> dialog`` that constructs the dialog
    against the supplied list of YAML files. ``load_instance_detail`` is
    stubbed to return a valid detail, and ``_run_next`` is replaced
    with a recorder so the test can assert call count without booting
    a worker.
    """
    from automation.ui.deployment import configure_progress
    from automation.ui.deployment.configure_progress import (
        ConfigureProgressDialog,
    )
    from automation.ui.deployment.deployment_logic import (
        InstanceDetail,
        InstanceRow,
    )

    def _stub_detail(_conn, _instance_id):
        return InstanceDetail(
            id=1,
            name="Test",
            code="T",
            environment="test",
            url="https://crm.example.com",
            username="admin",
            password="pw",
            description=None,
            is_default=False,
            created_at=None,
            updated_at=None,
        )

    monkeypatch.setattr(
        configure_progress, "load_instance_detail", _stub_detail
    )

    instance = InstanceRow(
        id=1, name="Test", code="T", environment="test",
        url="https://crm.example.com", is_default=False,
    )

    def _factory(files):
        # Replace _run_next on the class so the dialog never tries to
        # spawn a real worker. The patched method records its calls.
        run_next_calls: list[int] = []

        def _fake_run_next(self):
            run_next_calls.append(1)
            self._finish()

        monkeypatch.setattr(
            ConfigureProgressDialog, "_run_next", _fake_run_next
        )
        dialog = ConfigureProgressDialog(
            files=files,
            operation="run",
            instance=instance,
            conn=None,
            output_entry=None,
            parent=None,
        )
        dialog._run_next_calls = run_next_calls  # type: ignore[attr-defined]
        return dialog

    return _factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_validation_failure_excludes_file_from_pending(
    patched_dialog, tmp_path,
):
    """A YAML with a ``type: link`` field is excluded from ``_pending``
    and recorded in ``_file_results`` with a validation-failed outcome."""
    bad = _make_yaml(tmp_path, "bad.yaml", _INVALID_LINK_YAML)
    dialog = patched_dialog([bad])

    assert dialog._pending == []
    assert bad.path in dialog._file_results
    outcome, _ = dialog._file_results[bad.path]
    assert outcome.startswith("Validation failed")
    assert dialog._run_next_calls == []


def test_validation_failure_emits_log_block(patched_dialog, tmp_path):
    """The log contains a VALIDATION FAILED header for the bad file
    plus one indented line per error."""
    bad = _make_yaml(tmp_path, "bad.yaml", _INVALID_LINK_YAML)
    dialog = patched_dialog([bad])

    log_text = dialog._log.toPlainText()
    assert "=== bad.yaml: VALIDATION FAILED" in log_text
    # The link-specific error message is indented two spaces.
    assert "  - " in log_text
    assert "declared in the top-level 'relationships:' block" in log_text


def test_mixed_batch_only_valid_files_run(patched_dialog, tmp_path):
    """When one file is valid and one is not, only the valid file is
    queued for the worker."""
    good = _make_yaml(tmp_path, "good.yaml", _VALID_YAML)
    bad = _make_yaml(tmp_path, "bad.yaml", _INVALID_LINK_YAML)
    dialog = patched_dialog([good, bad])

    assert len(dialog._pending) == 1
    queued_file, _program = dialog._pending[0]
    assert queued_file.path == good.path
    assert bad.path in dialog._file_results
    assert good.path not in dialog._file_results
    assert dialog._run_next_calls == [1]


def test_all_invalid_batch_finishes_without_running(
    patched_dialog, tmp_path,
):
    """When every file fails validation, ``_run_next`` is never called
    and the log shows the all-invalid message."""
    bad1 = _make_yaml(tmp_path, "bad1.yaml", _INVALID_LINK_YAML)
    bad2 = _make_yaml(tmp_path, "bad2.yaml", _INVALID_LINK_YAML)
    dialog = patched_dialog([bad1, bad2])

    assert dialog._pending == []
    assert dialog._run_next_calls == []
    log_text = dialog._log.toPlainText()
    assert "all files failed validation" in log_text


def test_validation_tooltip_truncation(patched_dialog, tmp_path):
    """A file with more than five validation errors gets a tooltip
    listing the first five plus ``... (N more)``."""
    file_info = _make_yaml(tmp_path, "stub.yaml", _VALID_YAML)
    dialog = patched_dialog([file_info])

    errors = [f"err {i}" for i in range(8)]
    dialog._record_validation_failure(file_info, errors)

    tooltip = dialog._file_tooltips[file_info.path]
    lines = tooltip.split("\n")
    assert lines[:5] == errors[:5]
    assert lines[5] == "... (3 more)"
    assert len(lines) == 6


def test_validation_tooltip_no_more_line_when_exactly_five(
    patched_dialog, tmp_path,
):
    """Five errors produce no ``... (N more)`` line."""
    file_info = _make_yaml(tmp_path, "stub.yaml", _VALID_YAML)
    dialog = patched_dialog([file_info])

    errors = [f"err {i}" for i in range(5)]
    dialog._record_validation_failure(file_info, errors)

    tooltip = dialog._file_tooltips[file_info.path]
    assert tooltip.split("\n") == errors
