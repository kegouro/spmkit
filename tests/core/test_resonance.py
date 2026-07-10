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


def test_effective_spring_constant() -> None:
    # k(x) = k(L)/(x/L)³ ; en el extremo (x/L=1) es k(L); más cerca de la base, mayor.
    assert resonance.effective_spring_constant(1.175, 1.0) == pytest.approx(1.175)
    assert resonance.effective_spring_constant(1.175, 0.5) == pytest.approx(1.175 / 0.125)
    with pytest.raises(ValueError):
        resonance.effective_spring_constant(1.0, 1.5)


def test_x_over_l_scales_mass() -> None:
    # Cargar más cerca de la base (x/L<1) → k(x) mayor → masa mayor (k(x)=k(L)/(x/L)³).
    t = np.array([0.0, 3600.0])
    f = np.array([72_800.0, 79_000.0])
    ev_tip = resonance.track_evaporation(t, f, 1.175, x_over_l=1.0)
    ev_mid = resonance.track_evaporation(t, f, 1.175, x_over_l=0.5)
    assert ev_mid.added_mass[0] == pytest.approx(ev_tip.added_mass[0] / 0.5**3, rel=1e-9)


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


# --------------------------------------------------------------------------- nuevos tests


def test_droplet_radius() -> None:
    """Verifica r = (3m/(4πρ))^(1/3) para una masa conocida."""
    density = 1000.0
    r_expected = 1e-6  # 1 µm
    m = density * (4.0 / 3.0) * np.pi * r_expected**3
    r = resonance.droplet_radius(m, density=density)
    assert float(r) == pytest.approx(r_expected, rel=1e-9)


def test_droplet_radius_array() -> None:
    """Verifica que funciona con arrays y que masas ≤ 0 dan radio 0."""
    density = 1000.0
    r_ref = np.array([1e-6, 2e-6, 3e-6])
    masses = density * (4.0 / 3.0) * np.pi * r_ref**3
    masses_with_neg = np.concatenate([[-1.0, 0.0], masses])
    radios = resonance.droplet_radius(masses_with_neg, density=density)
    assert radios[0] == pytest.approx(0.0)
    assert radios[1] == pytest.approx(0.0)
    assert radios[2:] == pytest.approx(r_ref, rel=1e-9)


def test_fit_d2_law_linear() -> None:
    """Verifica ley d² con datos exactamente lineales: R²≈1, K correcto."""
    # Parámetros: r0 = 50 µm, τ = 2 h, K = d0²/τ
    r0 = 50e-6  # m
    tau = 2.0 * 3600.0  # s
    d0_sq = (2.0 * r0) ** 2
    K_true = d0_sq / tau  # m²/s

    t = np.linspace(0, tau * 0.9, 50)
    d2 = d0_sq - K_true * t
    r = np.sqrt(np.maximum(d2, 0.0)) / 2.0

    result = resonance.fit_d2_law(t, r)
    assert result.is_diffusion_limited is True
    assert result.r_squared == pytest.approx(1.0, abs=1e-10)
    assert result.rate_constant == pytest.approx(K_true, rel=1e-6)
    assert result.r0 == pytest.approx(r0, rel=1e-6)


def test_fit_sho_recovers_f0() -> None:
    """fit_sho recupera f0, Q y amplitud de pico en un espectro SHO sintético.

    La ASD es de magnitud minúscula (~1e-12 m/√Hz, como una ASD real calibrada):
    guarda contra la regresión de escala que hacía a ``curve_fit`` "converger" en
    la adivinanza inicial (Q y amplitud basura). Ruido en cuadratura, como el modelo.
    """
    pytest.importorskip("scipy")

    f0_true = 75_000.0  # Hz
    Q_true = 120.0
    A_true = 5e-12
    noise_floor = 1e-13

    f = np.linspace(60e3, 90e3, 2000)
    denom = (f**2 - f0_true**2) ** 2 + (f0_true * f / Q_true) ** 2
    psd = np.sqrt(A_true**2 * f0_true**4 / denom + noise_floor**2)  # potencia en cuadratura

    rng = np.random.default_rng(42)
    psd += rng.normal(0, noise_floor * 0.05, psd.size)

    peak = resonance.fit_sho(f, psd)
    assert peak.f0 == pytest.approx(f0_true, rel=5e-3)  # f0 dentro del 0.5 %
    assert peak.q_factor == pytest.approx(Q_true, rel=0.1)  # Q dentro del 10 %
    # amplitude = ASD en resonancia = A·Q (semántica de find_resonance).
    assert peak.amplitude == pytest.approx(A_true * Q_true, rel=0.1)
