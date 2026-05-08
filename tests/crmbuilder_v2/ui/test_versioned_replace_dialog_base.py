"""Skeleton test for VersionedReplaceDialog. Slice E will replace the
class body with the full JSON-payload-editor implementation; this test
documents the slice-A skeleton state.
"""

from __future__ import annotations

import pytest

from crmbuilder_v2.ui.base.versioned_replace_dialog import VersionedReplaceDialog


def test_skeleton_raises_until_slice_e_lands(qapp, qtbot):
    with pytest.raises(NotImplementedError, match="slice E"):
        VersionedReplaceDialog(
            current_payload={},
            save_callback=lambda payload: payload,
            title="Skeleton",
        )
