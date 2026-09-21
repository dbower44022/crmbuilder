"""The metadata write does not exist — PI-545 (REQ-632).

It never worked: the route it named accepts reads only. Three managers called
it, each behind an entry point that reports the platform limit and returns, so
none of those calls could run; nine tests asserted the call never happened.

Those nine proved nothing once the method was gone, because the client they
asserted against is a stand-in that answers to any name — the assertion would
have passed just as happily against a typo. This asserts the thing that is
now true and checkable: the real client has no such method.
"""

from __future__ import annotations

from espo_impl.core.api_client import EspoAdminClient


def test_the_client_has_no_metadata_write() -> None:
    assert not hasattr(EspoAdminClient, "put_metadata")


def test_the_managers_cannot_reach_a_write_at_all() -> None:
    """Each manager stops at its entry point, so nothing below it survives to
    call anything. Named here so a future reader sees why the three modules are
    a fifth of their former length."""
    from espo_impl.core import (
        duplicate_check_manager,
        saved_view_manager,
        workflow_manager,
    )

    for module, manager in (
        (saved_view_manager, "SavedViewManager"),
        (duplicate_check_manager, "DuplicateCheckManager"),
        (workflow_manager, "WorkflowManager"),
    ):
        names = [n for n in vars(getattr(module, manager)) if n.startswith("_process")]
        assert names == [], f"{manager} still carries {names}"
