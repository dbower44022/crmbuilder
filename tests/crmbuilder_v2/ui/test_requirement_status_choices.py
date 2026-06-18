"""PI-228: the requirement edit dialog must not offer ``confirmed`` as a target.

Confirming is done by recording an approving decision (the
``requirement_approved_by_decision`` edge → ``activate_by_decision``), never by
editing the status field. ``status_choices`` therefore drops ``confirmed`` from
the selectable values — except when it is already the current value, so an
already-confirmed requirement still renders correctly.
"""

from __future__ import annotations

from crmbuilder_v2.ui.dialogs._requirement_schema import status_choices


def test_confirmed_not_offered_from_candidate():
    choices = status_choices("candidate")
    assert "confirmed" not in choices
    assert "deferred" in choices  # the real successors remain


def test_confirmed_not_offered_from_deferred():
    assert "confirmed" not in status_choices("deferred")


def test_confirmed_still_shown_when_already_current():
    # An already-confirmed requirement must render its current value.
    assert "confirmed" in status_choices("confirmed")


def test_create_default_excludes_confirmed():
    # The create dialog starts at candidate (current=None) — no confirmed.
    assert "confirmed" not in status_choices(None)
