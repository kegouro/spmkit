"""Tests for conservative, version-scoped Gwyddion source-audit profiles."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from spmkit.compat.gwyddion.errors import UnsupportedGwyddionProfileError
from spmkit.compat.gwyddion.profiles import (
    GwyddionVersion,
    gwyddion_2_71_profile,
    profile_for_version,
)


def test_gwyddion_2_71_profile_is_immutable_and_conservative() -> None:
    profile = gwyddion_2_71_profile()
    assert str(profile.version) == "2.71"
    assert "GWY_MODULE_QUERY2" in profile.registration_calls
    assert "gwy_tool_func_register" in profile.registration_calls
    assert profile.mapping_dict["gwy_data_field_get_xres"] == "SPMChannel.shape[1]"
    assert "gwy_data_field_area_filter_min_max" not in profile.mapping_dict
    with pytest.raises(FrozenInstanceError):
        profile.name = "other"  # type: ignore[misc]


def test_profile_lookup_never_approximates_an_unsupported_version() -> None:
    assert profile_for_version(GwyddionVersion(2, 71)) == gwyddion_2_71_profile()
    with pytest.raises(UnsupportedGwyddionProfileError):
        profile_for_version(GwyddionVersion(2, 72))
    with pytest.raises(TypeError):
        profile_for_version("2.71")  # type: ignore[arg-type]
