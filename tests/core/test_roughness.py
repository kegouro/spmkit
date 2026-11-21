"""Tests de rugosidad."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from spmkit.core.analysis import roughness
from spmkit.core.models import SPMChannel


def test_sq_matches_known_sigma(flat_noisy: SPMChannel) -> None:
    # Para ruido gaussiano de sigma=2, Sq (RMS) debe acercarse a 2.
    result = roughness.statistics(flat_noisy)
    assert result.Sq == np.std(flat_noisy.data)
    assert abs(result.Sq - 2.0) < 0.1


def test_flat_surface_zero_roughness() -> None:
    ch = SPMChannel(name="Z", data=np.full((16, 16), 5.0), unit="m", x_range=1e-6, y_range=1e-6)
    r = roughness.statistics(ch)
    assert r.Sa == 0.0
    assert r.Sq == 0.0
    assert r.Sz == 0.0
    assert r.Ssk == 0.0  # guardia contra división por cero


def test_sa_sq_exact_values() -> None:
    data = np.array([[1.0, 2.0], [3.0, 4.0]])
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)
    r = roughness.statistics(ch)
    assert r.Sa == pytest.approx(1.0)
    assert r.Sq == pytest.approx(np.sqrt(1.25))
    assert r.unit == "m"
    assert r.n_points == 4


def test_sz_is_peak_to_valley() -> None:
    data = np.zeros((8, 8))
    data[0, 0] = 10.0
    data[1, 1] = -4.0
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)
    r = roughness.statistics(ch)
    assert r.Sz == r.Sp - r.Sv


def test_roughness_result_to_dict(flat_noisy: SPMChannel) -> None:
    d = roughness.statistics(flat_noisy).to_dict()
    assert {"Sa", "Sq", "Sz", "Ssk", "Sku", "unit", "n_points"} <= set(d)


def test_gaussian_moments() -> None:
    """Para una superficie gaussiana Ssk≈0 y Sku≈3 (referencia analítica)."""
    rng = np.random.default_rng(42)
    data = rng.normal(0.0, 1e-9, size=(256, 256))
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)
    r = roughness.statistics(ch)
    assert r.Ssk == pytest.approx(0.0, abs=0.05)
    assert r.Sku == pytest.approx(3.0, abs=0.1)


def test_statistics_ignores_isolated_nan() -> None:
    data = np.array([[1.0, 2.0], [3.0, np.nan]])
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)

    result = roughness.statistics(ch)

    assert result.Sq == pytest.approx(np.std([1.0, 2.0, 3.0]))
    assert result.n_points == 3


def test_statistics_rejects_all_nan_without_numpy_warnings() -> None:
    ch = SPMChannel(name="Z", data=np.full((2, 2), np.nan), unit="m", x_range=1e-6, y_range=1e-6)

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(ValueError, match="sin datos finitos"):
            roughness.statistics(ch)
