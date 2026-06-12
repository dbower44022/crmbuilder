"""Shared test fixtures for the espo_impl test suite."""

import os

# Pin the offscreen Qt platform for every pytest invocation, regardless of
# target subset or collection order (PI-159 §5.1). Individual Qt test
# modules also setdefault this ad hoc, but only after their own collection;
# the root conftest is the one file every run imports first. setdefault —
# not assignment — so an operator exporting a real platform for local
# visual debugging keeps their override.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
