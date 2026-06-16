"""Simulador del gemelo digital del cantiléver AFM.

Modela el espectro de ruido térmico (densidad espectral de amplitud, ASD) de
un oscilador armónico simple (SHO) y el corrimiento de frecuencia al añadir
masa en la punta — fenómeno observado experimentalmente durante la evaporación
de muestras.

Física del oscilador armónico:
    * Resonancia natural:  ``f0 = (1/2π) √(k / m_eff)``
    * Con masa añadida:    ``f = (1/2π) √(k / (m_eff + Δm))``
                           equivalente a ``f = f0 / √(1 + Δm/m_eff)``

Densidad espectral de potencia (PSD) del ruido térmico (teorema fluctuación-disipación):
    ``S_x(f) = C · g(f)``
    donde ``g(f) = f0⁴ / ((f² − f0²)² + (f0·f/Q)²)``
    y C se determina por equipartición: ``∫ S_x df = k_B T / k``.

La ASD (densidad espectral de amplitud) es ``ASD(f) = √S_x(f)`` en m/√Hz.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_BOLTZMANN = 1.380649e-23  # J/K (constante de Boltzmann exacta, SI 2019)


# ---------------------------------------------------------------- física básica


def thermal_spectrum(
    frequency: np.ndarray,
    f0: float,
    q_factor: float,
    spring_constant: float,
    temperature: float = 293.15,
) -> np.ndarray:
    """Densidad espectral de amplitud (ASD) del ruido térmico de un SHO.

    Calcula la ASD (m/√Hz) del ruido térmico de un oscilador armónico simple
    normalizada por el teorema de equipartición de energía::

        ⟨x²⟩ = k_B T / k  →  ∫ S_x(f) df = k_B T / k

    Forma espectral del SHO::

        g(f) = f0⁴ / ((f² − f0²)² + (f0·f/Q)²)

    Constante de normalización::

        C = (k_B T / k) / ∫ g(f) df

    Densidad espectral de potencia (PSD) y de amplitud (ASD)::

        S_x(f) = C · g(f)     [m²/Hz]
        ASD(f) = √S_x(f)      [m/√Hz]

    Args:
        frequency: Array de frecuencias (Hz), debe ser ≥ 0.
        f0: Frecuencia de resonancia (Hz).
        q_factor: Factor de calidad Q del oscilador (adimensional, > 0).
        spring_constant: Constante de resorte k (N/m, > 0).
        temperature: Temperatura T (K); por defecto 293.15 K (20 °C).

    Returns:
        Array de la misma forma que ``frequency`` con la ASD en m/√Hz.
    """
    frequency = np.asarray(frequency, dtype=np.float64)
    f2 = frequency**2
    f04 = f0**4
    denom = (f2 - f0**2) ** 2 + (f0 * frequency / q_factor) ** 2
    # Evitar división por cero en f=0 o en puntos degenerados
    g = np.where(denom > 0.0, f04 / denom, 0.0)

    # Normalización por equipartición: ∫ g df = k_B T / k / C
    g_integral = float(np.trapezoid(g, frequency))
    if g_integral <= 0.0:
        return np.zeros_like(frequency)
    C = (_BOLTZMANN * temperature / spring_constant) / g_integral

    psd = C * g  # m²/Hz
    return np.sqrt(np.maximum(psd, 0.0))  # m/√Hz


def loaded_frequency(f0_bare: float, spring_constant: float, added_mass: float) -> float:
    """Frecuencia de resonancia del cantiléver con masa añadida.

    Derivación::

        m_eff = k / (2π f0_bare)²
        f = (1/2π) √(k / (m_eff + Δm))
          = f0_bare / √(1 + Δm / m_eff)

    Args:
        f0_bare: Frecuencia del cantiléver desnudo (Hz, > 0).
        spring_constant: Constante de resorte k (N/m, > 0).
        added_mass: Masa añadida Δm (kg, ≥ 0).

    Returns:
        Nueva frecuencia de resonancia (Hz).

    Raises:
        ValueError: Si ``added_mass < 0`` o si el denominador resulta ≤ 0
            (situación no física).
    """
    if added_mass < 0.0:
        raise ValueError(f"added_mass debe ser ≥ 0; se recibió {added_mass}")
    if f0_bare <= 0.0:
        raise ValueError(f"f0_bare debe ser > 0; se recibió {f0_bare}")
    if spring_constant <= 0.0:
        raise ValueError(f"spring_constant debe ser > 0; se recibió {spring_constant}")

    m_eff = spring_constant / (2.0 * np.pi * f0_bare) ** 2
    ratio = 1.0 + added_mass / m_eff
    if ratio <= 0.0:
        raise ValueError(
            f"El denominador √(1 + Δm/m_eff) = √{ratio:.6g} es ≤ 0. "
            "Verifica que spring_constant y f0_bare sean físicamente razonables."
        )
    return float(f0_bare / np.sqrt(ratio))


# ---------------------------------------------------------------- dataclass


@dataclass(frozen=True)
class SimulatedCantilever:
    """Resultado de una simulación del gemelo digital del cantiléver.

    Atributos:
        frequency: Eje de frecuencias (Hz).
        asd_bare: ASD del cantiléver desnudo (m/√Hz).
        asd_loaded: ASD del cantiléver con masa añadida (m/√Hz).
        f0_bare: Resonancia del cantiléver desnudo (Hz).
        f0_loaded: Resonancia con masa añadida (Hz).
        added_mass: Masa añadida Δm (kg).
    """

    frequency: np.ndarray
    asd_bare: np.ndarray
    asd_loaded: np.ndarray
    f0_bare: float
    f0_loaded: float
    added_mass: float

    def to_dict(self) -> dict:
        """Serializa a diccionario con listas (compatible con JSON)."""
        return {
            "frequency_Hz": self.frequency.tolist(),
            "asd_bare_m_sqrtHz": self.asd_bare.tolist(),
            "asd_loaded_m_sqrtHz": self.asd_loaded.tolist(),
            "f0_bare_Hz": self.f0_bare,
            "f0_loaded_Hz": self.f0_loaded,
            "added_mass_kg": self.added_mass,
        }


# ---------------------------------------------------------------- función principal


def simulate(
    f0_bare: float = 75e3,
    q_factor: float = 100.0,
    spring_constant: float = 1.0,
    added_mass: float = 0.0,
    temperature: float = 293.15,
    n: int = 2000,
    f_max: float | None = None,
) -> SimulatedCantilever:
    """Simula el espectro de ruido térmico del cantiléver desnudo y cargado.

    Construye un eje de frecuencia ``[0, f_max]`` con ``n`` puntos, calcula la
    frecuencia de resonancia con masa añadida y genera los dos espectros ASD.

    Args:
        f0_bare: Frecuencia de resonancia del cantiléver desnudo (Hz).
        q_factor: Factor de calidad Q.
        spring_constant: Constante de resorte k (N/m).
        added_mass: Masa añadida Δm (kg); 0 → ambos espectros son idénticos.
        temperature: Temperatura T (K).
        n: Número de puntos del eje de frecuencia.
        f_max: Límite superior de frecuencia (Hz). Por defecto 2·f0_bare.

    Returns:
        :class:`SimulatedCantilever` con los dos espectros y metadatos.
    """
    if f_max is None:
        f_max = 2.0 * f0_bare

    frequency = np.linspace(0.0, f_max, n)

    f0_loaded = loaded_frequency(f0_bare, spring_constant, added_mass)

    asd_bare = thermal_spectrum(frequency, f0_bare, q_factor, spring_constant, temperature)
    asd_loaded = thermal_spectrum(frequency, f0_loaded, q_factor, spring_constant, temperature)

    return SimulatedCantilever(
        frequency=frequency,
        asd_bare=asd_bare,
        asd_loaded=asd_loaded,
        f0_bare=f0_bare,
        f0_loaded=f0_loaded,
        added_mass=added_mass,
    )
