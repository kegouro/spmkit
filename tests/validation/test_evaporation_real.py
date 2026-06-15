"""Validación con datos reales de evaporación de liquid marbles (thermal tuning)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spmkit import load
from spmkit.core.analysis import resonance

_DIR = Path(__file__).parents[2] / "reference" / "sample_files" / "evaporacion_resonancia"
_FILES = sorted(_DIR.glob("*.nid")) if _DIR.exists() else []

pytestmark = pytest.mark.skipif(len(_FILES) < 2, reason="sin datos de evaporación")


def test_extract_thermal_metadata() -> None:
    s = resonance.extract_thermal(load(_FILES[0]))
    assert s.spring_constant == pytest.approx(1.175, rel=0.01)
    assert 70e3 < s.f0 < 75e3
    assert s.psd.size > 1000
    assert s.timestamp is not None


def test_peak_matches_instrument() -> None:
    # El pico que detectamos debe coincidir con la frecuencia reportada.
    s = resonance.extract_thermal(load(_FILES[0]))
    peak = resonance.find_resonance(s.frequency, s.psd, f_min=50e3, f_max=99e3)
    assert peak.f0 == pytest.approx(s.f0, rel=0.01)


def test_evaporation_series_physics() -> None:
    ev = resonance.load_evaporation_series(_FILES)
    assert len(ev.time) == len(_FILES)
    # La frecuencia sube con el tiempo (la masa baja al evaporarse).
    assert ev.frequency[-1] > ev.frequency[0]
    # La masa de la liquid marble es del orden de ~1 ng.
    assert 0.1e-12 < ev.added_mass[0] < 5e-12
    # Δm decrece hasta ~0 al final.
    assert ev.added_mass[-1] < ev.added_mass[0]
    assert np.isfinite(ev.evaporation_rate).all()
