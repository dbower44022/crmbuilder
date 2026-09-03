"""The emitter and the deploy engine agree on what a value means — PI-461.

REQ-558 / DEC-1016. Every other test in this package reads an emitted program
back with ruamel, the same dialect that wrote it, so a disagreement between the
writer and the real reader is invisible to them by construction. These tests
read with the engine's own loader instead.
"""

from __future__ import annotations

import io
import pathlib
import tempfile

import pytest
import yaml as pyyaml
from crmbuilder_v2.adapters.espocrm.emit import _YAML_11_BOOLEANS, _yaml

from espo_impl.core.config_loader import ConfigLoader


def _emit(payload: dict) -> str:
    buf = io.StringIO()
    _yaml().dump(payload, buf)
    return buf.getvalue()


def _round_trip(payload: dict):
    """Emit as the adapter does, read as the deploy engine does."""
    return pyyaml.safe_load(_emit(payload))


@pytest.mark.parametrize("word", sorted(_YAML_11_BOOLEANS))
def test_a_word_the_engine_would_read_as_a_bool_survives_as_text(word):
    for spelling in (word, word.upper(), word.capitalize()):
        assert _round_trip({"v": spelling})["v"] == spelling, spelling


def test_an_enum_option_list_of_yes_and_no_is_not_deployed_as_true_and_false():
    """The case that makes this worth fixing. A design offering Yes and No is
    ordinary, and before this the instance received booleans instead — nothing
    raised, the option list was simply wrong."""
    options = ["Yes", "No", "Unknown"]
    back = _round_trip({"fields": [{"name": "isActive", "options": options}]})
    assert back["fields"][0]["options"] == options


def test_real_booleans_stay_booleans():
    """The fix quotes strings; it must not turn a genuine flag into text, or a
    field declared required would arrive as the string 'true'."""
    back = _round_trip({"required": True, "readOnly": False})
    assert back["required"] is True
    assert back["readOnly"] is False


def test_nothing_else_gains_quotes():
    """Scoped to the version gap: ruamel already quotes what the 1.2 resolver
    would reclaim, so ordinary text, numbers and the y/n abbreviations PyYAML
    leaves alone are untouched."""
    text = _emit({"a": "all", "b": "Mentor Role", "c": "y", "d": "n"})
    assert "'" not in text, text


def test_the_engine_loads_a_program_whose_option_labels_are_yes_and_no():
    """End to end through the loader the Configure flow actually uses, not just
    through safe_load."""
    program = {
        "version": "1.0.0",
        "description": "dialect probe",
        "content_version": "1.0.0",
        "entities": {
            "Contact": {
                "action": "update",
                "fields": [{
                    "name": "cSubscribed",
                    "type": "enum",
                    "label": "Subscribed",
                    "options": ["Yes", "No"],
                }],
            },
        },
    }
    path = pathlib.Path(tempfile.mkdtemp()) / "Dialect-Probe.yaml"
    path.write_text(_emit(program))

    loaded = ConfigLoader().load_program(path)
    field = loaded.entities[0].fields[0]
    assert field.options == ["Yes", "No"]
