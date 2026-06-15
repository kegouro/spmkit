"""Tests de resonancia y sensado de masa."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import resonance


def test_parse_quantity() -> None:
    assert resonance.parse_quantity("72,8kHz") == pytest.approx(72800.0)
    assert resonance.parse_quantity("1,175 N/m") == pytest.approx(1.175)
    assert resonance.parse_quantity("1,19pm/sqrt(Hz)") == pytest.approx(1.19e-12)
    assert resonance.parse_quantity("106 ") == pytest.approx(106.0)
    assert resonance.parse_quantity("20 °C") == pytest.approx(20.0)


def test_effective_mass_roundtrip() -> None:
    # m = k/(2πf)²  →  f = (1/2π)√(k/m) recupera la masa
    k, m = 1.175, 5.0e-12
    f = (1 / (2 * np.pi)) * np.sqrt(k / m)
    assert resonance.effective_mass(k, f) == pytest.approx(m, rel=1e-9)


def test_added_mass_sign() -> None:
    # Frecuencia menor que la desnuda → masa añadida positiva
    k = 1.175
    dm = resonance.added_mass(k, frequency=72_800, bare_frequency=79_000)
    assert dm > 0
    assert dm == pytest.approx(0.85e-12, rel=0.1)  # ~0.85 ng


def test_added_mass_zero_at_bare() -> None:
    assert resonance.added_mass(1.0, 80_000, 80_000) == pytest.approx(0.0, abs=1e-20)


def test_find_resonance_synthetic() -> None:
    # Lorentziana con pico en 75 kHz
    f = np.linspace(50e3, 100e3, 2000)
    f0_true, q = 75e3, 100
    psd = 1.0 / np.sqrt((f**2 - f0_true**2) ** 2 + (f0_true * f / q) ** 2)
    peak = resonance.find_resonance(f, psd)
    assert peak.f0 == pytest.approx(f0_true, rel=2e-3)
    assert peak.q_factor > 0


def test_track_evaporation() -> None:
    # f sube de 72.8 a 79 kHz → Δm baja a 0; tasa finita
    t = np.array([0.0, 1800.0, 3600.0, 7200.0])
    f = np.array([72_800.0, 76_000.0, 78_500.0, 79_000.0])
    ev = resonance.track_evaporation(t, f, spring_constant=1.175)
    assert ev.bare_frequency == 79_000.0
    assert ev.added_mass[0] > ev.added_mass[-1]
    assert ev.added_mass[-1] == pytest.approx(0.0, abs=1e-20)
    assert ev.evaporation_rate.shape == t.shape


def test_track_evaporation_mismatch() -> None:
    with pytest.raises(ValueError, match="mismo tamaño"):
        resonance.track_evaporation(np.zeros(3), np.zeros(4), 1.0)
