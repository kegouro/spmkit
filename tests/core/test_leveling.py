"""Tests de nivelación."""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis import leveling
from spmkit.core.models import SPMChannel


def test_plane_fit_removes_tilt(tilted_surface: SPMChannel) -> None:
    leveled = leveling.plane_fit(tilted_surface)
    # Tras quitar el plano, la media debe ser ~0 y el rango mucho menor.
    assert abs(leveled.data.mean()) < 1e-6
    assert np.ptp(leveled.data) < np.ptp(tilted_surface.data)


def test_plane_fit_preserves_metadata(tilted_surface: SPMChannel) -> None:
    leveled = leveling.plane_fit(tilted_surface)
    assert leveled.unit == tilted_surface.unit
    assert leveled.x_range == tilted_surface.x_range
    assert leveled.shape == tilted_surface.shape


def test_polynomial_flattens_curvature() -> None:
    rows = cols = 32
    yy, xx = np.mgrid[0:rows, 0:cols]
    bowl = (xx - 16) ** 2 + (yy - 16) ** 2
    ch = SPMChannel(name="Z", data=bowl.astype(float), unit="m", x_range=1e-6, y_range=1e-6)
    leveled = leveling.polynomial(ch, order=2)
    assert np.allclose(leveled.data, 0.0, atol=1e-6)


def test_align_rows() -> None:
    data = np.zeros((10, 10))
    data += np.arange(10).reshape(-1, 1)  # offset por fila
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)
    leveled = leveling.align_rows(ch, method="median")
    assert np.allclose(leveled.data, 0.0)
