"""Tests de perfiles de línea."""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis import profiles
from spmkit.core.models import SPMChannel


def test_horizontal_profile_constant() -> None:
    data = np.tile(np.arange(10, dtype=float), (10, 1))  # gradiente en X
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)
    prof = profiles.line(ch, (0, 5), (9, 5), n=10)
    assert np.allclose(prof.height, np.arange(10))
    assert len(prof) == 10


def test_profile_distance_physical() -> None:
    data = np.zeros((10, 10))
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)
    prof = profiles.line(ch, (0, 0), (9, 0), n=10)
    # 9 pasos de píxel * (1e-6/10) m/píxel
    assert prof.distance[-1] == np.hypot(9 * ch.pixel_size_x, 0.0)


def test_bilinear_midpoint() -> None:
    data = np.array([[0.0, 2.0], [0.0, 2.0]])
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)
    prof = profiles.line(ch, (0.5, 0), (0.5, 0), n=1)
    assert prof.height[0] == 1.0
