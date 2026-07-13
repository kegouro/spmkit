"""Tests de perfiles de línea."""

from __future__ import annotations

import numpy as np
import pytest

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


def test_diagonal_profile_uses_anisotropic_physical_ranges() -> None:
    ch = SPMChannel(name="Z", data=np.zeros((4, 4)), unit="m", x_range=2e-6, y_range=6e-6)

    prof = profiles.line(ch, (0, 0), (3, 3), n=4)

    expected = np.hypot(3 * ch.pixel_size_x, 3 * ch.pixel_size_y)
    assert prof.distance[-1] == pytest.approx(expected)


def test_profile_rejects_non_spatial_channel() -> None:
    ch = SPMChannel(name="Spectrum", data=np.zeros((1, 4)), unit="V", x_range=1.0, y_range=1.0)

    with pytest.raises(ValueError, match="espacial"):
        profiles.line(ch, (0, 0), (3, 0))


@pytest.mark.parametrize("n", [0, -1])
def test_profile_rejects_sample_count_below_one(n: int) -> None:
    ch = SPMChannel(name="Z", data=np.zeros((2, 2)), unit="m", x_range=1e-6, y_range=1e-6)

    with pytest.raises(ValueError, match="n debe ser >= 1"):
        profiles.line(ch, (0, 0), (1, 1), n=n)


@pytest.mark.parametrize(
    ("p0", "p1"),
    [
        ((-0.1, 0), (1, 1)),
        ((0, -0.1), (1, 1)),
        ((0, 0), (2, 1)),
        ((0, 0), (1, 2)),
    ],
)
def test_profile_rejects_endpoints_outside_image(
    p0: tuple[float, float], p1: tuple[float, float]
) -> None:
    ch = SPMChannel(name="Z", data=np.zeros((2, 2)), unit="m", x_range=1e-6, y_range=1e-6)

    with pytest.raises(ValueError, match="fuera"):
        profiles.line(ch, p0, p1, n=2)
