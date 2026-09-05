"""Publish dialog — push the canonical design to a target instance (PRJ-042).

A two-phase modal: it first **validates** the generated design against the live
target (``POST /publish-validate``) and renders a per-program report; the
**Publish** button stays disabled until every program is valid (REQ-288). On
confirm it **deploys** (``POST /publish``) and renders the per-program result
with summary counts. Both phases run off the UI thread via
:func:`run_in_thread`; the render helpers are pure so they are unit-tested
directly.

The access gate (REQ-521 / PI-468). A publish carries the security program,
so it changes who can reach what on the target. The preview states that
effect — each role against the live target, removals flagged, or *unknown*
when the target could not be read — and hands the dialog the plan
fingerprint. A publish that follows a preview is a **reviewed run**: it sends
that fingerprint, and the confirmation box states the effect in the same
words. A removal is put to the operator as a second, separate question, and
``confirm_access_removal`` is sent only when that question is answered yes —
never on the dialog's own initiative. A publish with no preview behind it is
an **automatic run** (DEC-982): it sends no fingerprint, only ever adds or
widens, and when the API declines a removal by name the dialog shows the
reasons and offers the reviewed path rather than a bare failure.
"""

from __future__ import annotations

import html
import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import ConflictError, StorageConnectionError
from crmbuilder_v2.ui.widgets.form_helpers import primary_button
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.publish_dialog")

_GREEN = "#1e8449"
_RED = "#c0392b"
_AMBER = "#b9770e"
_MUTE = "#888"


def _esc(value: object) -> str:
    return html.escape(str(value))


def _summary_counts(summary: dict | None) -> str:
    """A compact human summary of the deploy counts for one program."""
    s = summary or {}
    bits: list[str] = []
    for key, label in (
        ("created", "created"),
        ("updated", "updated"),
        ("skipped", "skipped"),
        ("relationships_created", "rel(s)"),
        ("layouts_updated", "layout(s)"),
        ("errors", "error(s)"),
    ):
        if s.get(key):
            bits.append(f"{s[key]} {label}")
    return ", ".join(bits)


def _header(phase: str, result: dict) -> str:
    target = _esc(result.get("target_instance", "?"))
    engine = _esc(result.get("engine", "?"))
    return (
        f"<h3 style='margin:0 0 4px 0'>{phase} &middot; {target} "
        f"<span style='color:{_MUTE}'>({engine})</span></h3>"
    )


# Friendly headings for the deferral ``kind`` groups, so the checklist names
# the EspoCRM construct an operator configures by hand rather than the raw
# internal kind token. Unknown kinds fall back to a title-cased label.
_DEFERRAL_KIND_LABELS = {
    "view": "Saved views",
    "workflow_action": "Workflows",
    "automation": "Automations / workflows",
    "dedup_rule": "Duplicate-check rules",
    "dedup_normalize": "Duplicate-check rules",
    "message_template": "Message templates",
    "entity_rule": "Dynamic-logic rules",
    "field_rule": "Dynamic-logic rules",
    "derived_field": "Derived (formula) fields",
    "reference_field": "Reference fields",
    "field_attribute": "Field attributes",
    "unmapped_field": "Unmapped fields",
}


def _kind_label(kind: str) -> str:
    return _DEFERRAL_KIND_LABELS.get(
        kind, str(kind).replace("_", " ").capitalize()
    )


def _deferral_line(item: dict) -> str:
    """One checklist row: ``☐ name (parent) — reason``."""
    name = _esc(item.get("name") or item.get("identifier") or "?")
    parent = item.get("parent")
    where = f" <span style='color:{_MUTE}'>({_esc(parent)})</span>" if parent else ""
    detail = item.get("detail")
    why = f" — {_esc(detail)}" if detail else ""
    return f"<li>&#9744; <b>{name}</b>{where}{why}</li>"


def render_manual_config_html(result: dict) -> str:
    """Render the manual-config checklist from the publish result (REQ-294).

    The publish/preview/validate result already carries structured
    ``deferrals`` — the design constructs EspoCRM cannot apply over the REST
    API (saved views, workflows, duplicate-check rules, message templates,
    dynamic-logic rules, derived/reference fields, …) — plus the adapter's
    ``MANUAL-CONFIG.md`` companion text. This turns them into a readable,
    grouped post-publish checklist so an operator knows exactly what is left
    to configure by hand. Returns ``""`` when there is nothing deferred.
    """
    defs = result.get("deferrals") or []
    if not defs:
        # No structured deferrals; note the companion only if it exists.
        if result.get("manual_config"):
            return (
                f"<p style='color:{_AMBER}'>A MANUAL-CONFIG.md companion was "
                f"generated for this design.</p>"
            )
        return ""

    groups: dict[str, list[dict]] = {}
    for item in defs:
        groups.setdefault(item.get("kind") or "other", []).append(item)

    parts = [
        f"<h4 style='margin:12px 0 4px 0;color:{_AMBER}'>&#9888; Manual "
        f"configuration required ({len(defs)} item(s))</h4>",
        "<p style='color:#555;margin:0 0 6px 0'>These are not applied "
        "automatically — configure them by hand in the target's admin UI:"
        "</p>",
    ]
    # Stable, human order: group by friendly label.
    for kind in sorted(groups, key=_kind_label):
        items = groups[kind]
        parts.append(
            f"<p style='margin:6px 0 2px 0'><b>{_esc(_kind_label(kind))}</b> "
            f"<span style='color:{_MUTE}'>({len(items)})</span></p>"
        )
        parts.append("<ul style='margin:0;padding-left:18px'>")
        parts.extend(_deferral_line(i) for i in items)
        parts.append("</ul>")
    return "".join(parts)


_VERIFY_GLYPH = {
    "matching": (_GREEN, "&#10003;"),  # ✓
    "partial": (_AMBER, "&#9656;"),  # ▸
    "missing": (_RED, "&#10007;"),  # ✗
    "unverified": (_MUTE, "?"),
}


def render_verification_html(result: dict) -> str:
    """Render the post-publish verification section (REQ-291).

    After a real publish the service re-reads the live target and confirms each
    declared entity + field landed; this renders that per-object result. Returns
    ``""`` when no verification ran (preview / validate-only).
    """
    verify = result.get("verification")
    if not verify or not verify.get("ran"):
        return ""
    entities = verify.get("entities") or []
    if verify.get("all_present"):
        head = (
            f"<h4 style='margin:12px 0 4px 0;color:{_GREEN}'>&#10003; "
            f"Verified on target — all {len(entities)} object(s) present.</h4>"
        )
    elif not verify.get("conclusive"):
        head = (
            f"<h4 style='margin:12px 0 4px 0;color:{_AMBER}'>&#9888; "
            f"Verification inconclusive — could not read the target's live "
            f"state.</h4>"
        )
    else:
        head = (
            f"<h4 style='margin:12px 0 4px 0;color:{_RED}'>&#10007; "
            f"Verification found gaps — some objects did not land.</h4>"
        )
    parts = [head, "<ul style='margin:0;padding-left:18px'>"]
    for ent in entities:
        status = ent.get("status", "unverified")
        color, glyph = _VERIFY_GLYPH.get(status, (_MUTE, "?"))
        name = _esc(ent.get("entity", "?"))
        missing = ent.get("fields_missing") or []
        if status == "missing":
            detail = "entity not found on target"
        elif missing:
            detail = f"missing field(s): {_esc(', '.join(missing))}"
        elif status == "unverified":
            detail = "not checked"
        else:
            n = len(ent.get("fields_present") or [])
            detail = f"{n} field(s) present"
        parts.append(
            f"<li><span style='color:{color}'>{glyph} {name}</span> — "
            f"{detail}</li>"
        )
    parts.append("</ul>")
    for w in verify.get("warnings") or []:
        parts.append(f"<p style='color:{_MUTE};margin:2px 0'>{_esc(w)}</p>")
    return "".join(parts)


# -- the access effect (REQ-521 / PI-468) ------------------------------------

#: The words the API uses for how the target holds a role right now
#: (``publish.access.LIVE_*``), rendered for the operator.
_LIVE_STATE_WORDS = {
    "present": "on the target today",
    "absent": "not on the target yet — created",
    "unknown": "state unknown — the target could not be read",
}


def access_removal_lines(section: dict | None) -> list[str]:
    """Each removal in the API's own words (``description``), in order."""
    return [
        c.get("description", "")
        for c in (section or {}).get("removals") or []
    ]


def access_change_lines(section: dict | None) -> list[str]:
    """Every access change in the API's own words, in order."""
    return [
        c.get("description", "")
        for c in (section or {}).get("changes") or []
    ]


def access_is_unknown(section: dict | None) -> bool:
    """True when the target could not be read, so the effect is not stated."""
    return bool(section) and bool(section.get("assessed")) and not section.get(
        "known", True
    )


def render_access_html(section: dict | None) -> str:
    """Render the ``access`` section of a preview or publish result.

    The words are the API's (``summary`` and each change's ``description``,
    e.g. ``Mentor: Contact.delete all → no``); this only lays them out — a
    summary line, then each role with its effect lines, a removal flagged in
    red, and an explicit *unknown* when the target could not be read, so the
    dialog never implies "no change" where nothing was proven. Returns ``""``
    when the result carries no section (a validate-only result).
    """
    if not section:
        return ""
    if not section.get("assessed"):
        return (
            f"<p style='color:{_MUTE};margin:8px 0 0 0'>&#128274; Access: "
            f"{_esc(section.get('summary') or 'no role or team is published.')}"
            f"</p>"
        )
    parts: list[str] = []
    if access_is_unknown(section):
        parts.append(
            f"<h4 style='margin:12px 0 4px 0;color:{_AMBER}'>&#9888; Access "
            f"effect unknown — the target could not be read.</h4>"
        )
        reason = section.get("reason")
        if reason:
            parts.append(
                f"<p style='color:{_AMBER};margin:0 0 4px 0'>{_esc(reason)}</p>"
            )
        parts.append(
            "<p style='color:#555;margin:0 0 4px 0'>Nothing is claimed either "
            "way. An automatic publish is refused while the effect is "
            "unknown; a reviewed publish proceeds on the approved plan and "
            "the deploy fails if the target still cannot be read.</p>"
        )
    else:
        removals = access_removal_lines(section)
        color = _RED if removals else _GREEN
        glyph = "&#10007;" if removals else "&#10003;"
        parts.append(
            f"<h4 style='margin:12px 0 4px 0;color:{color}'>{glyph} Access: "
            f"{_esc(section.get('summary') or '')}</h4>"
        )
        if removals:
            parts.append(
                f"<p style='color:{_RED};margin:0 0 4px 0'>This publish takes "
                f"away access the instance currently grants. It is never "
                f"applied automatically — Publish will ask you to confirm "
                f"each removal separately.</p>"
            )
    for role in section.get("roles") or []:
        name = _esc((role.get("target") or {}).get("member_name") or "?")
        state = _LIVE_STATE_WORDS.get(role.get("live_state") or "", "")
        where = f" <span style='color:{_MUTE}'>({state})</span>" if state else ""
        parts.append(
            f"<p style='margin:6px 0 2px 0'><b>Role {name}</b>{where}</p>"
        )
        changes = role.get("changes") or []
        if role.get("live_state") == "unknown":
            parts.append(
                f"<p style='color:{_AMBER};margin:0 0 0 18px'>effect unknown "
                f"— {_esc(role.get('summary') or '')}</p>"
            )
            continue
        if not changes:
            parts.append(
                f"<p style='color:{_MUTE};margin:0 0 0 18px'>"
                f"{_esc(role.get('summary') or 'no access setting changes.')}"
                f"</p>"
            )
            continue
        parts.append("<ul style='margin:0;padding-left:18px'>")
        for change in changes:
            line = _esc(change.get("description") or "")
            if change.get("removes_access"):
                parts.append(
                    f"<li style='color:{_RED}'>&#10007; {line} "
                    f"<b>— removes access</b></li>"
                )
            else:
                parts.append(f"<li>&#9656; {line}</li>")
        parts.append("</ul>")
    for team in section.get("teams") or []:
        name = _esc((team.get("target") or {}).get("member_name") or "?")
        parts.append(
            f"<p style='margin:6px 0 2px 0'><b>Team {name}</b> "
            f"<span style='color:{_MUTE}'>{_esc(team.get('summary') or '')}"
            f"</span></p>"
        )
    return "".join(parts)


def render_declined_html(result: dict) -> str:
    """Render an automatic run's declined changes (REQ-497 / DEC-982).

    The API declines a removal, narrowing or type change by name on a run
    that carries no approved plan; this shows each in the API's words and
    names the way through — Preview, then Publish — instead of a bare
    failure. Returns ``""`` when nothing was declined.
    """
    declined = result.get("declined_changes") or []
    if not declined:
        return ""
    parts = [
        f"<h4 style='margin:12px 0 4px 0;color:{_RED}'>&#10007; Not applied "
        f"— an automatic publish may only add or widen "
        f"({len(declined)} change(s) declined).</h4>",
        "<ul style='margin:0;padding-left:18px'>",
    ]
    for d in declined:
        construct = _esc(d.get("construct") or "?")
        kind = _esc(d.get("kind") or "change")
        reason = _esc(d.get("reason") or "")
        parts.append(
            f"<li><b>{construct}</b>: {kind}"
            f"{' — ' + reason if reason else ''}</li>"
        )
    parts.append("</ul>")
    parts.append(
        "<p style='color:#555;margin:4px 0 0 0'>Nothing was written. To carry "
        "these deliberately, click <b>Preview</b> to review the plan and its "
        "access effect, then <b>Publish</b> for a reviewed run; a change "
        "that takes access away is confirmed separately.</p>"
    )
    return "".join(parts)


def render_refused_html(result: dict, target: str) -> str:
    """Render the API's 409 refusal of a reviewed run that takes access away
    without the separate word (REQ-521): its message verbatim, and the way
    through."""
    parts = [
        f"<h3 style='margin:0 0 4px 0'>Publish refused &middot; {_esc(target)}"
        f"</h3>",
        f"<p style='color:{_RED}'>{_esc(result.get('message') or '')}</p>",
        "<p style='color:#555'>Nothing was written. Click <b>Preview</b> to "
        "review the access effect, then <b>Publish</b> and confirm the "
        "removal when asked.</p>",
    ]
    return "".join(parts)


def render_validate_html(result: dict) -> str:
    """Render the validate-phase report as rich text."""
    programs = result.get("programs", [])
    parts = [_header("Validate", result)]
    parts.append(
        f"<p style='color:#555'>{len(programs)} program(s) generated.</p>"
    )
    parts.append("<ul style='margin:0;padding-left:18px'>")
    for p in programs:
        fn = _esc(p.get("filename", "?"))
        errs = p.get("validation_errors") or []
        if errs:
            parts.append(
                f"<li><span style='color:{_RED}'>&#10007; {fn}</span> — "
                f"{len(errs)} error(s):<ul>"
            )
            parts.extend(
                f"<li style='color:{_RED}'>{_esc(e)}</li>" for e in errs
            )
            parts.append("</ul></li>")
        else:
            parts.append(
                f"<li><span style='color:{_GREEN}'>&#10003; {fn}</span> — "
                f"valid</li>"
            )
    parts.append("</ul>")
    parts.append(render_manual_config_html(result))
    if result.get("validation_failed"):
        parts.append(
            f"<p style='color:{_RED};font-weight:bold'>Fix the errors above "
            f"before publishing.</p>"
        )
    else:
        parts.append(
            f"<p style='color:{_GREEN};font-weight:bold'>All programs valid "
            f"— ready to publish.</p>"
        )
    return "".join(parts)


def _backup_note(result: dict) -> str:
    """A one-line note on the pre-publish backup / abort state (REQ-292).

    An abort is not always the backup gate: the plan can have moved since the
    preview (REQ-496), or the run can have been declined or held for an
    access effect (REQ-521); those say so in the API's words and are not told
    to override the backup gate.
    """
    if result.get("aborted"):
        reason = _esc(result.get("abort_reason") or "the target could not be "
                      "backed up")
        if result.get("declined_changes"):
            return ""  # render_declined_html carries the reasons
        if result.get("plan_moved") or access_is_unknown(result.get("access")):
            return (
                f"<p style='color:{_RED};font-weight:bold'>&#10007; Publish "
                f"not run — {reason}</p>"
            )
        return (
            f"<p style='color:{_RED};font-weight:bold'>&#10007; Publish "
            f"aborted — {reason}. Nothing was written. Re-try, or override the "
            f"backup gate to publish without a backup.</p>"
        )
    run = result.get("publish_run")
    run_note = f" Recorded as {_esc(run)}." if run else ""
    if result.get("backup_captured"):
        return (
            f"<p style='color:{_MUTE}'>&#128190; Target backed up before "
            f"publishing.{run_note}</p>"
        )
    return (
        f"<p style='color:{_AMBER}'>Published without a target backup.{run_note}"
        f"</p>"
    )


def render_publish_html(result: dict) -> str:
    """Render the publish-phase report as rich text."""
    parts = [_header("Publish", result)]
    if result.get("aborted"):
        parts.append(_backup_note(result))
        parts.append(render_declined_html(result))
        return "".join(parts)
    programs = result.get("programs", [])
    parts.append("<ul style='margin:0;padding-left:18px'>")
    for p in programs:
        fn = _esc(p.get("filename", "?"))
        if p.get("deployed"):
            counts = _summary_counts(p.get("summary"))
            suffix = f" ({counts})" if counts else ""
            parts.append(
                f"<li><span style='color:{_GREEN}'>&#10003; {fn}</span> — "
                f"deployed{suffix}</li>"
            )
        else:
            errs = p.get("validation_errors") or []
            reason = (
                f"{len(errs)} validation error(s)" if errs else "not deployed"
            )
            parts.append(
                f"<li><span style='color:{_RED}'>&#10007; {fn}</span> — "
                f"{_esc(reason)}</li>"
            )
    parts.append("</ul>")
    parts.append(_backup_note(result))
    parts.append(render_access_html(result.get("access")))
    parts.append(render_verification_html(result))
    parts.append(render_manual_config_html(result))
    return "".join(parts)


def _preview_counts(summary: dict | None) -> str:
    """The actions a program WOULD take, from its dry-run report summary."""
    s = summary or {}
    bits: list[str] = []
    for key, label in (
        ("created", "create"),
        ("updated", "update"),
        ("relationships_created", "relationship(s)"),
        ("layouts_updated", "layout(s)"),
    ):
        if s.get(key):
            bits.append(f"{s[key]} {label}")
    unchanged = (
        (s.get("skipped") or 0)
        + (s.get("layouts_skipped") or 0)
        + (s.get("relationships_skipped") or 0)
    )
    if unchanged:
        bits.append(f"{unchanged} unchanged")
    return ", ".join(bits) or "no changes"


def render_preview_html(result: dict) -> str:
    """Render the preview (dry-run) plan as rich text."""
    programs = result.get("programs", [])
    parts = [_header("Preview", result)]
    parts.append(
        f"<p style='color:{_GREEN}'>Non-destructive — nothing was written "
        f"to the target.</p>"
    )
    parts.append("<ul style='margin:0;padding-left:18px'>")
    for p in programs:
        fn = _esc(p.get("filename", "?"))
        errs = p.get("validation_errors") or []
        if errs:
            parts.append(
                f"<li><span style='color:{_RED}'>&#10007; {fn}</span> — "
                f"{len(errs)} validation error(s)</li>"
            )
        else:
            parts.append(
                f"<li><span style='color:{_AMBER}'>&#9656; {fn}</span> — "
                f"would: {_esc(_preview_counts(p.get('summary')))}</li>"
            )
    parts.append("</ul>")
    parts.append(render_access_html(result.get("access")))
    fp = result.get("plan_fingerprint")
    if fp:
        parts.append(
            f"<p style='color:{_MUTE};margin:8px 0 0 0'>Plan {_esc(fp)} — "
            f"Publish now runs this reviewed plan.</p>"
        )
    parts.append(render_manual_config_html(result))
    return "".join(parts)


def _publish_failed(result: dict) -> bool:
    if result.get("aborted"):
        return True
    if bool(result.get("validation_failed")) or any(
        not p.get("deployed") for p in result.get("programs", [])
    ):
        return True
    # A conclusive post-publish verify that found missing objects is an issue
    # even when every program reported "deployed" (REQ-291).
    verify = result.get("verification") or {}
    if verify.get("ran") and verify.get("conclusive") and not verify.get(
        "all_present"
    ):
        return True
    return False


class PublishDialog(QDialog):
    """Two-phase validate-then-deploy dialog for a target instance."""

    def __init__(self, client, instance_record: dict, parent=None) -> None:
        super().__init__(parent)
        self._client = client
        self._record = instance_record
        self._identifier = instance_record.get("instance_identifier")
        self._target_name = (
            instance_record.get("instance_name") or self._identifier
        )
        self._can_publish = False
        self._worker = None
        # The reviewed-run handoff (REQ-521 / DEC-982): the plan fingerprint
        # and access section the last preview returned for the current scope.
        # ``None`` means no preview stands behind the next publish, which then
        # runs automatic (no fingerprint, additive-only). Dropped whenever the
        # plan can have moved: a re-validate, a scope change, a publish.
        self._plan_fingerprint: str | None = None
        self._access: dict | None = None

        self.setWindowTitle(f"Publish design → {self._target_name}")
        self.resize(680, 500)

        layout = QVBoxLayout(self)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # Scope selector (REQ-290): the operator can uncheck programs to
        # publish only a subset. Populated from the validate result.
        self._scope_label = QLabel("Publish scope (uncheck to exclude):")
        layout.addWidget(self._scope_label)
        self._scope_list = QListWidget()
        self._scope_list.setObjectName("publish_scope_list")
        self._scope_list.setMaximumHeight(110)
        self._scope_list.itemChanged.connect(self._on_scope_changed)
        layout.addWidget(self._scope_list)

        self._results = QTextEdit()
        self._results.setReadOnly(True)
        self._results.setObjectName("publish_results")
        layout.addWidget(self._results, 1)

        # Backup-gate override (REQ-292): off by default — a publish backs up
        # the target first and aborts if it can't, unless this is checked.
        self._allow_no_backup = QCheckBox(
            "Publish even if the target can't be backed up"
        )
        self._allow_no_backup.setObjectName("allow_no_backup_checkbox")
        layout.addWidget(self._allow_no_backup)

        row = QHBoxLayout()
        self._revalidate_btn = QPushButton("Re-validate")
        self._revalidate_btn.setObjectName("revalidate_button")
        self._revalidate_btn.clicked.connect(self._start_validate)
        self._preview_btn = QPushButton("Preview")
        self._preview_btn.setObjectName("preview_button")
        self._preview_btn.setToolTip(
            "Show what publishing would change — without writing anything."
        )
        self._preview_btn.clicked.connect(self._start_preview)
        self._publish_btn = primary_button("Publish ▶")
        self._publish_btn.setObjectName("publish_button")
        self._publish_btn.clicked.connect(self._on_publish_clicked)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        row.addWidget(self._revalidate_btn)
        row.addWidget(self._preview_btn)
        row.addStretch(1)
        row.addWidget(self._publish_btn)
        row.addWidget(close_btn)
        layout.addLayout(row)

        self._set_busy(False, can_publish=False)
        self._start_validate()

    # -- state -----------------------------------------------------------

    def _set_busy(self, busy: bool, *, can_publish: bool | None = None) -> None:
        if can_publish is not None:
            self._can_publish = can_publish
        self._busy = busy
        self._revalidate_btn.setEnabled(not busy)
        self._preview_btn.setEnabled(not busy)
        self._publish_btn.setEnabled(
            not busy and self._can_publish and self._has_selection()
        )

    # -- scope selection (REQ-290) ---------------------------------------

    def _populate_scope(
        self,
        programs: list[dict],
        default_checked: set[str] | None = None,
    ) -> None:
        """Fill the scope list from the validate result, preserving any prior
        unchecked selections (a re-validate keeps the operator's choices).

        On the first populate, ``default_checked`` (the instance's stored
        feature selection resolved to filenames, REQ-546 / PI-444) pre-checks
        only those programs; ``None`` keeps the check-everything default.
        """
        fresh = self._scope_list.count() == 0
        prev_unchecked = {
            self._scope_list.item(i).text()
            for i in range(self._scope_list.count())
            if self._scope_list.item(i).checkState() != Qt.CheckState.Checked
        }
        self._scope_list.blockSignals(True)
        self._scope_list.clear()
        for p in programs:
            fn = p.get("filename", "?")
            item = QListWidgetItem(fn)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if fresh and default_checked is not None:
                checked = fn in default_checked
            else:
                checked = fn not in prev_unchecked
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            self._scope_list.addItem(item)
        self._scope_list.blockSignals(False)

    def _has_selection(self) -> bool:
        return any(
            self._scope_list.item(i).checkState() == Qt.CheckState.Checked
            for i in range(self._scope_list.count())
        )

    def _selected_scope(self) -> list[str] | None:
        """The checked filenames, or ``None`` when everything is selected
        (publish the whole design — the default, sends no scope)."""
        total = self._scope_list.count()
        checked = [
            self._scope_list.item(i).text()
            for i in range(total)
            if self._scope_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if total == 0 or len(checked) == total:
            return None
        return checked

    def _on_scope_changed(self, _item) -> None:
        # A different scope is a different plan: the previewed fingerprint no
        # longer names what would be sent, so the next publish is automatic
        # until the operator previews again.
        self._drop_reviewed_plan()
        # Re-evaluate the Publish button (needs at least one selected program).
        self._publish_btn.setEnabled(
            not getattr(self, "_busy", False)
            and self._can_publish
            and self._has_selection()
        )

    # -- the reviewed-run handoff (REQ-521 / DEC-982) --------------------

    def _drop_reviewed_plan(self) -> None:
        self._plan_fingerprint = None
        self._access = None

    def is_reviewed(self) -> bool:
        """True when a preview stands behind the next publish, so it runs as
        the reviewed run (with the plan fingerprint) rather than automatic."""
        return self._plan_fingerprint is not None

    # -- validate phase --------------------------------------------------

    def _start_validate(self) -> None:
        self._drop_reviewed_plan()
        self._status.setText("Validating the design against the target…")
        self._set_busy(True)
        self._worker = run_in_thread(
            lambda: self._client.publish_validate_instance(self._identifier),
            on_success=self._on_validated,
            on_error=self._on_error,
            parent=self,
        )

    def _on_validated(self, result: dict[str, Any]) -> None:
        self._results.setHtml(render_validate_html(result))
        # The full program list drives the scope selector (validate is always
        # run full-scope so every program is selectable). The instance's stored
        # feature selection, when present, pre-checks the list (REQ-546 /
        # PI-444) — the operator sees and can override what a bare publish
        # would send.
        selection = result.get("feature_selection") or None
        default_checked = (
            set(selection.get("filenames") or []) if selection else None
        )
        self._populate_scope(
            result.get("programs", []), default_checked=default_checked
        )
        if selection:
            note = (
                "Publish scope — pre-checked from this instance's stored "
                "feature selection:"
            )
            unresolved = selection.get("unresolved") or []
            if unresolved:
                note = note[:-1] + (
                    f" ({len(unresolved)} stored entr"
                    f"{'y' if len(unresolved) == 1 else 'ies'} no longer in "
                    "the design):"
                )
            self._scope_label.setText(note)
        ok = not result.get("validation_failed", True)
        self._status.setText(
            "Validation passed — ready to publish."
            if ok
            else "Validation failed — fix the errors before publishing."
        )
        self._set_busy(False, can_publish=ok)

    # -- preview phase (non-destructive dry-run) -------------------------

    def _start_preview(self) -> None:
        self._status.setText("Previewing — building the plan (no writes)…")
        self._set_busy(True)
        scope = self._selected_scope()
        self._worker = run_in_thread(
            lambda: self._client.publish_preview_instance(
                self._identifier, scope
            ),
            on_success=self._on_previewed,
            on_error=self._on_error,
            parent=self,
        )

    def _on_previewed(self, result: dict[str, Any]) -> None:
        if result.get("validation_failed"):
            self._drop_reviewed_plan()
            self._results.setHtml(render_validate_html(result))
            self._status.setText(
                "Validation failed — fix the errors before publishing."
            )
            self._set_busy(False, can_publish=False)
            return
        self._results.setHtml(render_preview_html(result))
        # The preview is how the fingerprint is obtained (DEC-982): the next
        # publish sends it and runs reviewed, carrying the access effect the
        # operator has just been shown.
        self._plan_fingerprint = result.get("plan_fingerprint") or None
        self._access = result.get("access")
        if access_removal_lines(self._access):
            status = (
                "Preview complete — nothing was written. This publish takes "
                "access away; Publish will ask you to confirm each removal."
            )
        elif access_is_unknown(self._access):
            status = (
                "Preview complete — nothing was written. The access effect "
                "is unknown because the target could not be read."
            )
        elif self._plan_fingerprint:
            status = (
                "Preview complete — nothing was written. Publish now runs "
                "the reviewed plan."
            )
        else:
            status = "Preview complete — nothing was written. Ready to publish."
        self._status.setText(status)
        self._set_busy(False, can_publish=True)

    # -- publish phase ---------------------------------------------------

    def _confirm_publish(self, scope: list[str] | None) -> bool:
        """The first question (REQ-521): the target and the effect.

        A reviewed run states the access effect the preview showed in the
        API's words — every change, a removal marked; an automatic run says
        it can only add or widen. Agreeing here is not agreeing to a removal;
        that is :meth:`_confirm_access_removal`'s separate question.
        """
        what = (
            "the canonical design"
            if scope is None
            else f"{len(scope)} selected program(s)"
        )
        lines = [f"Deploy {what} to {self._target_name}?"]
        if self.is_reviewed():
            lines.append(f"\nReviewed run — plan {self._plan_fingerprint}.")
            access = self._access or {}
            if access.get("assessed"):
                lines.append(access.get("summary") or "")
                removals = set(access_removal_lines(access))
                for line in access_change_lines(access):
                    mark = "  (removes access)" if line in removals else ""
                    lines.append(f"• {line}{mark}")
        else:
            lines.append(
                "\nAutomatic run — no preview approved. It only adds or "
                "widens: a change that removes, narrows or lowers access is "
                "declined by name. Click Preview first to review and carry "
                "such changes."
            )
        lines.append("\nThis writes configuration to the live instance.")
        confirm = CopyableMessageBox(self)
        confirm.setWindowTitle("Confirm publish")
        confirm.setText("\n".join(lines))
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return confirm.exec() == QMessageBox.StandardButton.Ok

    def _confirm_access_removal(self) -> bool:
        """The second, separate question (REQ-521), asked only when the
        previewed plan takes access away — the same words as the Reconcile
        grid's gate. Yes is the only thing that makes the dialog send
        ``confirm_access_removal``.
        """
        removals = access_removal_lines(self._access)
        answer = CopyableMessageBox.warning(
            self, "This removes access",
            "This publish takes away access the instance currently grants. It "
            "is never applied without a separate, deliberate confirmation.\n\n"
            + "\n".join(f"• {line}" for line in removals)
            + "\n\nRemove this access on " + str(self._target_name) + "?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _on_publish_clicked(self) -> None:
        scope = self._selected_scope()
        if not self._confirm_publish(scope):
            return
        fingerprint = self._plan_fingerprint
        confirm_removal = False
        if self.is_reviewed() and access_removal_lines(self._access):
            if not self._confirm_access_removal():
                self._status.setText(
                    "Publish not run — the access removal was not confirmed; "
                    "nothing was sent."
                )
                return
            confirm_removal = True
        allow_no_backup = self._allow_no_backup.isChecked()
        self._status.setText(f"Backing up + publishing to {self._target_name}…")
        self._set_busy(True)
        # The plan is spent once sent: a further publish previews again.
        self._drop_reviewed_plan()
        self._worker = run_in_thread(
            lambda: self._client.publish_instance(
                self._identifier, scope, allow_no_backup,
                expected_plan_fingerprint=fingerprint,
                confirm_access_removal=confirm_removal,
            ),
            on_success=self._on_published,
            on_error=self._on_error,
            parent=self,
        )

    def _on_published(self, result: dict[str, Any]) -> None:
        self._results.setHtml(render_publish_html(result))
        if result.get("declined_changes"):
            n = len(result["declined_changes"])
            status = (
                f"Publish declined — {n} change(s) need a reviewed run. "
                "Click Preview to review them, then Publish."
            )
        elif result.get("aborted") and result.get("plan_moved"):
            status = (
                "Publish not run — the plan has moved since the preview. "
                "Click Preview to review the new plan, then Publish."
            )
        elif result.get("aborted") and access_is_unknown(result.get("access")):
            status = (
                "Publish not run — the access effect is unknown because the "
                "target could not be read. Click Preview when it can be read, "
                "then Publish."
            )
        elif result.get("aborted"):
            status = "Publish aborted — the target could not be backed up."
        elif _publish_failed(result):
            status = "Publish finished with issues — see the report."
        else:
            status = "Publish complete."
        self._status.setText(status)
        # A fresh validate is required before another publish.
        self._set_busy(False, can_publish=False)

    # -- errors ----------------------------------------------------------

    def _on_error(self, exc: Exception) -> None:
        if isinstance(exc, ConflictError):
            # REQ-521: the API refused a reviewed run that takes access away
            # without the separate word (the removal was not in the preview
            # this dialog showed, or the target has changed since). Shown in
            # the API's words, with the way through, not as a failure.
            _log.info("Publish refused by the access gate: %s", exc)
            self._results.setHtml(
                render_refused_html({"message": str(exc)}, self._target_name)
            )
            self._status.setText(
                "Publish refused — it takes access away that was not "
                "confirmed. Click Preview, then Publish and confirm the "
                "removal."
            )
            self._set_busy(False, can_publish=False)
            return
        _log.warning("Publish operation failed: %s", exc)
        title = (
            "Connection lost"
            if isinstance(exc, StorageConnectionError)
            else "Operation failed"
        )
        ErrorDialog(
            title=title,
            message="The publish operation could not complete.",
            detail=str(exc),
            parent=self,
        ).exec()
        self._status.setText("Operation failed.")
        self._set_busy(False)
