"""Tests de la figura de mapas de propiedades de force-volume."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("matplotlib")

from spmkit.core.viz.maps import save_property_maps  # noqa: E402


def test_save_property_maps_creates_png(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    maps = {
        "young_modulus": rng.uniform(1e5, 2e6, size=(8, 8)),
        "adhesion": rng.uniform(1e-9, 5e-9, size=(8, 8)),
    }
    out = tmp_path / "maps.png"
    result = save_property_maps(maps, out, title="test")
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 1000  # PNG no trivial


def test_save_property_maps_all_nan_raises(tmp_path: Path) -> None:
    maps = {"young_modulus": np.full((4, 4), np.nan)}
    with pytest.raises(ValueError, match="graficable"):
        save_property_maps(maps, tmp_path / "x.png")
