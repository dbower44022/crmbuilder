"""Shared test fixtures for the espo_impl test suite."""

import os

import pytest

# Pin the offscreen Qt platform for every pytest invocation, regardless of
# target subset or collection order (PI-159 §5.1). Individual Qt test
# modules also setdefault this ad hoc, but only after their own collection;
# the root conftest is the one file every run imports first. setdefault —
# not assignment — so an operator exporting a real platform for local
# visual debugging keeps their override.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item):
    """Reclaim leaked Qt widgets at EVERY test boundary (PI-159 follow-up).

    PI-159 added a deferred-deletion drain, but only in the UI-subtree
    conftest (``tests/crmbuilder_v2/ui/conftest.py``). The SIGSEGV it chased
    actually fires in pytest-qt's post-test ``_process_events`` of *unrelated,
    often non-UI* tests: pytest-qt's ``qapp`` is session-scoped, so once any UI
    test creates it the application persists and processes events for every
    subsequent test. A widget leaked by an earlier UI test — one never handed
    to ``qtbot.addWidget``, so never ``deleteLater``'d and thus invisible to a
    DeferredDelete-only drain — is freed by Python GC at a non-deterministic
    later point, and a queued paint event then dereferences the half-destructed
    C++ object. The subtree-scoped hook cannot help a test outside the subtree.

    This global hook closes the window for the whole suite: force a GC so any
    unreferenced Qt object's C++ destructor runs *now*, then drain the
    resulting deferred deletions and process events, so nothing crosses into
    the next test with a pending paint. A bounded loop settles deletions that
    post further deletions. No-op when no QApplication exists (pure-logic
    tests never pay for it; the import stays lazy so non-Qt runs do not load
    PySide6 at collection time).
    """
    try:
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication
    except Exception:
        return
    app = QApplication.instance()
    if app is None:
        return
    import gc

    for _ in range(3):
        gc.collect()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
