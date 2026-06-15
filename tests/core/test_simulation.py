"""Tests del simulador del gemelo digital del cantiléver.

Verifica la corrección física de:
- Normalización por equipartición del espectro térmico.
- Corrimiento de frecuencia al añadir masa.
- Consistencia con la masa efectiva.
- Desplazamiento del pico en la simulación completa.
"""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis.simulation import (
    _BOLTZMANN,
    SimulatedCantilever,
    loaded_frequency,
    simulate,
    thermal_spectrum,
)

# ---------------------------------------------------------------- utilidades


def _effective_mass(spring_constant: float, f0: float) -> float:
    """m_eff = k / (2π f0)²."""
    return spring_constant / (2.0 * np.pi * f0) ** 2


# ---------------------------------------------------------------- tests


def test_equipartition() -> None:
    """La integral de la PSD (ASD²) debe ser ≈ k_B T / k (equipartición).

    Tolerancia relativa del 5 %.
    """
    f0 = 75e3  # Hz
    q = 150.0
    k = 1.5  # N/m
    T = 300.0  # K

    n = 4000
    freq = np.linspace(0.0, 2.0 * f0, n)
    asd = thermal_spectrum(freq, f0, q, k, T)

    psd = asd**2  # m²/Hz
    integral = float(np.trapezoid(psd, freq))

    expected = _BOLTZMANN * T / k
    rel_error = abs(integral - expected) / expected
    assert rel_error < 0.05, (
        f"Equipartición: integral={integral:.3e}, esperado={expected:.3e}, "
        f"error relativo={rel_error:.2%}"
    )


def test_loaded_frequency_lower() -> None:
    """Añadir masa positiva baja la frecuencia de resonancia."""
    f0 = 75e3  # Hz
    k = 1.0  # N/m
    dm = 1e-12  # 1 ng

    f_loaded = loaded_frequency(f0, k, dm)
    assert f_loaded < f0, f"loaded_frequency={f_loaded:.1f} Hz no es < f0={f0:.1f} Hz"


def test_loaded_frequency_matches_effective_mass() -> None:
    """Con Δm = m_eff, la frecuencia cargada debe ser f0/√2.

    De la fórmula: f = f0 / √(1 + Δm/m_eff)
    Si Δm = m_eff → f = f0 / √2.
    """
    f0 = 75e3  # Hz
    k = 1.0  # N/m
    m_eff = _effective_mass(k, f0)

    f_loaded = loaded_frequency(f0, k, m_eff)
    expected = f0 / np.sqrt(2.0)

    rel_error = abs(f_loaded - expected) / expected
    assert rel_error < 1e-6, (
        f"f_loaded={f_loaded:.6f} Hz, esperado f0/√2={expected:.6f} Hz, "
        f"error relativo={rel_error:.2e}"
    )


def test_simulate_peaks() -> None:
    """En simulate con added_mass > 0, el pico de asd_loaded está a menor frecuencia."""
    result: SimulatedCantilever = simulate(
        f0_bare=75e3,
        q_factor=100.0,
        spring_constant=1.0,
        added_mass=1e-12,  # 1 ng
        temperature=293.15,
    )

    peak_bare = float(result.frequency[int(np.argmax(result.asd_bare))])
    peak_loaded = float(result.frequency[int(np.argmax(result.asd_loaded))])

    assert peak_loaded < peak_bare, (
        f"Pico cargado ({peak_loaded / 1e3:.3f} kHz) no es < pico desnudo "
        f"({peak_bare / 1e3:.3f} kHz). La masa debe bajar la frecuencia."
    )
