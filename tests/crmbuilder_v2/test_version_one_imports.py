"""The version 1 imports version 2 still makes may shrink, never grow
(REQ-604 / PI-517).

Nothing in version 1 can be deleted while version 2 imports it, and the
inventory approved under DEC-1093 lists what each remaining import costs. The
goal is an empty list; until the apply engine is absorbed the list cannot be
empty, so this test freezes it instead. Removing an import means deleting its
line here — which is the point: the list is the deletion gate made visible.

A new import of version 1 from version 2 fails this test. If one is genuinely
needed, it belongs in the inventory with a disposition first.
"""

from __future__ import annotations

import ast
import pathlib

#: Package roots that make a module part of version 1.
_VERSION_ONE_ROOTS = frozenset({"espo_impl", "automation"})

#: Every version 1 module version 2 still imports, by the file that imports it,
#: with the requirement that will remove it. Ordered by that requirement.
_PERMITTED: frozenset[tuple[str, str]] = frozenset(
    {
        # REQ-606 — version 2 parses and validates a declaration itself.
        ("adapters/espocrm/adapter.py", "espo_impl.core.config_loader"),
        ("publish/service.py", "espo_impl.core.config_loader"),
        ("publish/access.py", "espo_impl.core.models"),
        ("publish/service.py", "espo_impl.core.models"),
        # REQ-605 — version 2 writes to a live CRM system through its own
        # client. The write client exists; the publish path adopts it when the
        # managers below are absorbed.
        ("publish/service.py", "espo_impl.core.api_client"),
        # REQ-608 — declared fields land, with the comparison REQ-609 covers.
        ("publish/service.py", "espo_impl.core.field_manager"),
        ("publish/service.py", "espo_impl.core.comparator"),
        # REQ-615 — the governed setting values and the design-version stamp.
        ("publish/service.py", "espo_impl.core.system_settings_manager"),
        # REQ-616 — the run report, step isolation and the manual-config list.
        ("publish/service.py", "espo_impl.core.deploy_pipeline"),
        # Area 4a of the inventory — the five provisioning phases, which the
        # deploy runner calls until upgrade and recovery are absorbed. Not yet
        # carried by a requirement; it is in the approved inventory.
        ("deploy/runner.py", "automation.core.deployment"),
    }
)

_PACKAGE_ROOT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "crmbuilder-v2"
    / "src"
    / "crmbuilder_v2"
)


def _version_one_imports() -> set[tuple[str, str]]:
    """Every (file, version 1 module) pair version 2 imports.

    Walks the whole syntax tree rather than the module header, because an
    import inside a function is still an import — two of the ones frozen above
    are exactly that.
    """
    found: set[tuple[str, str]] = set()
    for path in sorted(_PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        where = str(path.relative_to(_PACKAGE_ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0] in _VERSION_ONE_ROOTS:
                    found.add((where, module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in _VERSION_ONE_ROOTS:
                        found.add((where, alias.name))
    return found


def test_no_new_version_one_import_appears() -> None:
    actual = _version_one_imports()
    new = sorted(actual - _PERMITTED)
    assert not new, (
        "version 2 gained an import of version 1: "
        + ", ".join(f"{where} imports {module}" for where, module in new)
        + ". Nothing in version 1 can be deleted while version 2 imports it — "
        "put the capability in the inventory with a disposition first."
    )


def test_the_permitted_list_names_nothing_already_gone() -> None:
    """A removed import must be struck from the list, or the gate stops
    measuring anything."""
    actual = _version_one_imports()
    stale = sorted(_PERMITTED - actual)
    assert not stale, (
        "these version 1 imports are gone and should be struck from the "
        "permitted list: "
        + ", ".join(f"{where} imports {module}" for where, module in stale)
    )


def test_no_version_two_module_imports_a_version_one_screen() -> None:
    """The user-interface package is the one part of version 1 version 2 must
    never reach into.

    It was reached: the publish path imported an entity-naming helper from a
    dialog module, which loaded the whole graphical toolkit inside the headless
    service that runs a publish. Version 2 has its own helper; this holds the
    door shut.
    """
    offenders = sorted(
        (where, module)
        for where, module in _version_one_imports()
        if ".ui" in module or module.endswith(".ui")
    )
    assert not offenders, (
        "version 2 imports a version 1 screen module: "
        + ", ".join(f"{where} imports {module}" for where, module in offenders)
    )
