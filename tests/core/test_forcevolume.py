"""Tests del análisis de force-volume (mapas de propiedades)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis.forcevolume import analyze_volume
from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume
from spmkit.core.pipeline import Recipe, Step

_NANOMECH_NID = (
    Path(__file__).resolve().parents[2]
    / "reference"
    / "sample_files"
    / "Image00860 nanomech small nanofiber.nid"
)

_RECIPE = Recipe(
    steps=(
        Step(op="find_contact_point"),
        Step(
            op="fit_elasticity",
            params={"model": "sphere", "tip_radius": 10e-9},
            condition="contact_detected",
        ),
    )
)


def _hertz_curve(young: float, radius: float = 10e-9, sep_contact: float = 3e-7) -> ForceCurve:
    sep = np.linspace(6e-7, 0.0, 400)
    e_star = young / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(radius)
    force = k * np.clip(sep_contact - sep, 0.0, None) ** 1.5
    seg = ForceSegment(
        segment_type="extend",
        direction="approach",
        raw_height=sep,
        raw_deflection=np.zeros_like(sep),
        force=force,
        separation=sep,
        state="force_n",
    )
    return ForceCurve(segments=(seg,))


def _synthetic_volume() -> ForceVolume:
    # grilla 2×2 con módulos conocidos crecientes
    moduli = [0.5e6, 1.0e6, 1.5e6, 2.0e6]
    curves = tuple(_hertz_curve(m) for m in moduli)
    return ForceVolume.from_curves(curves, grid_shape=(2, 2), x_range=1e-6, y_range=1e-6)


def test_analyze_volume_recovers_modulus_map() -> None:
    result = analyze_volume(_synthetic_volume(), _RECIPE)
    assert result.n_ok == 4
    assert result.n_failed == 0
    emap = result.maps["young_modulus"]
    assert emap.shape == (2, 2)
    expected = np.array([[0.5e6, 1.0e6], [1.5e6, 2.0e6]])
    assert np.allclose(emap, expected, rtol=0.05)


def test_volume_stats_and_histogram() -> None:
    result = analyze_volume(_synthetic_volume(), _RECIPE)
    s = result.stats("young_modulus")
    assert s["n"] == 4
    assert s["median"] == pytest.approx(1.25e6, rel=0.05)
    counts, edges = result.histogram("young_modulus", bins=4)
    assert counts.sum() == 4


def test_parallel_matches_sequential() -> None:
    vol = _synthetic_volume()
    seq = analyze_volume(vol, _RECIPE, parallel=False)
    par = analyze_volume(vol, _RECIPE, parallel=True, max_workers=2)
    assert np.allclose(seq.maps["young_modulus"], par.maps["young_modulus"], equal_nan=True)


@pytest.mark.skipif(not _NANOMECH_NID.exists(), reason="sample .nid de nanomecánica no disponible")
def test_analyze_real_nid_volume() -> None:
    from spmkit.core.io import load_nid_force

    vol = load_nid_force(_NANOMECH_NID)
    result = analyze_volume(vol, _RECIPE)
    assert result.grid_shape == (10, 10)
    assert result.n_ok >= 1
    assert result.maps["young_modulus"].shape == (10, 10)
    assert np.isfinite(result.maps["young_modulus"]).any()
