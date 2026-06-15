"""Resonancia del cantiléver y sensado de masa por desplazamiento de frecuencia.

Un cantiléver es un oscilador armónico: ``f0 = (1/2π)·√(k/m_eff)``. Al añadir
masa en la punta (p.ej. una *liquid marble*), ``f0`` baja; al evaporarse la
masa, ``f0`` vuelve a la del cantiléver desnudo. De ahí:

* Masa efectiva:        ``m_eff = k / (2π·f0)²``
* Masa añadida:         ``Δm = m_eff(f) − m_eff(f_desnuda)``
                          ``   = (k/4π²)·(1/f² − 1/f_desnuda²)``
* Aproximación lineal:  ``Δf/f0 ≈ −Δm / (2·m_eff)``   →  ``Δf ∝ Δm``

Este módulo lee los espectros de *thermal tuning* de NanoSurf (frecuencia vs
densidad espectral de amplitud), detecta la resonancia, y sigue la masa y la
**tasa de evaporación** ``dΔm/dt`` a lo largo de una serie temporal.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from spmkit.core.models import SPMData

# Prefijos SI para parsear valores tipo "72,8kHz" o "1,19pm/sqrt(Hz)".
_SI_PREFIX = {"p": 1e-12, "n": 1e-9, "µ": 1e-6, "u": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6, "G": 1e9}


def parse_quantity(text: str) -> float:
    """Convierte un valor de NanoSurf a SI: ``"72,8kHz"`` → ``72800.0``.

    Maneja coma decimal y un prefijo SI opcional pegado a la unidad
    (``k``, ``m``, ``p``, ``n``, ``µ``, ``M``, ``G``). ``"1,175 N/m"`` → ``1.175``.
    """
    s = text.strip().replace(",", ".")
    m = re.match(r"[-+]?[0-9]*\.?[0-9]+", s)
    if not m:
        raise ValueError(f"No se pudo parsear un número de: {text!r}")
    value = float(m.group())
    rest = s[m.end() :].strip()
    if rest and rest[0] in _SI_PREFIX and len(rest) > 1 and rest[1].isalpha():
        value *= _SI_PREFIX[rest[0]]
    return value


@dataclass(frozen=True)
class ResonancePeak:
    """Pico de resonancia detectado en un espectro."""

    f0: float  # frecuencia de resonancia (Hz)
    q_factor: float  # factor de calidad
    amplitude: float  # amplitud del pico (unidad del espectro)
    fwhm: float  # ancho a media altura (Hz)


@dataclass(frozen=True)
class ThermalSpectrum:
    """Espectro de *thermal tuning* de un cantiléver en un instante."""

    frequency: np.ndarray  # Hz
    psd: np.ndarray  # densidad espectral de amplitud (m/√Hz)
    fit: np.ndarray | None  # ajuste del instrumento, si existe
    f0: float  # resonancia reportada (Hz)
    q_factor: float
    spring_constant: float  # N/m
    temperature_c: float  # °C
    timestamp: datetime | None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EvaporationSeries:
    """Serie temporal del sensado de masa durante una evaporación."""

    time: np.ndarray  # s, relativo al primer punto
    frequency: np.ndarray  # Hz (resonancia en cada instante)
    mass: np.ndarray  # kg (masa efectiva total)
    added_mass: np.ndarray  # kg (respecto al cantiléver desnudo)
    evaporation_rate: np.ndarray  # kg/s (dΔm/dt)
    spring_constant: float  # N/m
    bare_frequency: float  # Hz (cantiléver desnudo)

    def to_dict(self) -> dict:
        return {
            "time_s": self.time.tolist(),
            "frequency_Hz": self.frequency.tolist(),
            "mass_kg": self.mass.tolist(),
            "added_mass_kg": self.added_mass.tolist(),
            "evaporation_rate_kg_s": self.evaporation_rate.tolist(),
            "spring_constant_N_m": self.spring_constant,
            "bare_frequency_Hz": self.bare_frequency,
        }


# --------------------------------------------------------------- física básica
def effective_mass(spring_constant: float, frequency: float) -> float:
    """Masa efectiva del modo: ``m = k / (2π·f)²`` (kg)."""
    if frequency <= 0:
        raise ValueError("frequency debe ser > 0")
    return spring_constant / (2.0 * np.pi * frequency) ** 2


def added_mass(spring_constant: float, frequency: float, bare_frequency: float) -> float:
    """Masa añadida respecto al cantiléver desnudo (kg).

    ``Δm = (k/4π²)·(1/f² − 1/f_desnuda²)``
    """
    return effective_mass(spring_constant, frequency) - effective_mass(
        spring_constant, bare_frequency
    )


# ------------------------------------------------------------ lectura/detección
def extract_thermal(data: SPMData) -> ThermalSpectrum:
    """Extrae un :class:`ThermalSpectrum` de un ``.nid`` de *thermal tuning*."""
    fft = next((c for c in data.channels if "FFT" in c.group), data.channels[0])
    fit_ch = next((c for c in data.channels if "Fit" in c.group), None)

    psd = np.asarray(fft.data, dtype=np.float64).ravel()
    f_range = float(fft.metadata.get("Dim0Range", psd.size))
    f_min = float(fft.metadata.get("Dim0Min", 0.0))
    frequency = f_min + np.linspace(0.0, f_range, psd.size)
    fit = np.asarray(fit_ch.data, dtype=np.float64).ravel() if fit_ch is not None else None

    info = data.metadata.get("info", {})
    f0 = parse_quantity(info["Frequency:"]) if "Frequency:" in info else float("nan")
    q = parse_quantity(info["Q Factor:"]) if "Q Factor:" in info else float("nan")
    k = parse_quantity(info["Spring Constant:"]) if "Spring Constant:" in info else float("nan")
    temp = parse_quantity(info.get("Cantilever temperature", "20")) if info else 20.0
    ts = _parse_timestamp(info.get("Date", ""), info.get("Time", ""))

    return ThermalSpectrum(
        frequency=frequency,
        psd=psd,
        fit=fit,
        f0=f0,
        q_factor=q,
        spring_constant=k,
        temperature_c=temp,
        timestamp=ts,
        metadata=dict(info),
    )


def find_resonance(
    frequency: np.ndarray, psd: np.ndarray, f_min: float | None = None, f_max: float | None = None
) -> ResonancePeak:
    """Detecta la resonancia en un espectro (pico + Q por ancho a media altura).

    Funciona solo con numpy. El pico es el máximo en ``[f_min, f_max]`` y el Q
    se estima del ancho a media altura (FWHM): ``Q = f0 / FWHM``.
    """
    frequency = np.asarray(frequency, dtype=np.float64)
    psd = np.asarray(psd, dtype=np.float64)
    mask = np.ones(frequency.size, dtype=bool)
    if f_min is not None:
        mask &= frequency >= f_min
    if f_max is not None:
        mask &= frequency <= f_max
    fr, pr = frequency[mask], psd[mask]
    if fr.size < 3:
        raise ValueError("Muy pocos puntos en el rango indicado")

    peak = int(np.argmax(pr))
    f0 = float(fr[peak])
    amp = float(pr[peak])
    half = amp / 2.0
    above = pr >= half
    idx = np.flatnonzero(above)
    fwhm = float(fr[idx[-1]] - fr[idx[0]]) if idx.size >= 2 else 0.0
    q = f0 / fwhm if fwhm > 0 else float("nan")
    return ResonancePeak(f0=f0, q_factor=q, amplitude=amp, fwhm=fwhm)


def _parse_timestamp(date: str, time: str) -> datetime | None:
    for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M"):
        try:
            return datetime.strptime(f"{date.strip()} {time.strip()}", fmt)
        except ValueError:
            continue
    return None


# ----------------------------------------------------------- serie de evaporación
def track_evaporation(
    time: np.ndarray,
    frequency: np.ndarray,
    spring_constant: float,
    bare_frequency: float | None = None,
) -> EvaporationSeries:
    """Calcula masa, masa añadida y tasa de evaporación a partir de ``f(t)``.

    Args:
        time: Tiempos (s), preferiblemente relativos al primer punto.
        frequency: Resonancia en cada instante (Hz).
        spring_constant: Constante de resorte del cantiléver (N/m).
        bare_frequency: Frecuencia del cantiléver desnudo (Hz). Por defecto, la
            frecuencia máxima de la serie (estado completamente evaporado).
    """
    time = np.asarray(time, dtype=np.float64)
    frequency = np.asarray(frequency, dtype=np.float64)
    if time.size != frequency.size:
        raise ValueError("time y frequency deben tener el mismo tamaño")
    bare = float(np.max(frequency)) if bare_frequency is None else bare_frequency

    mass = spring_constant / (2.0 * np.pi * frequency) ** 2
    bare_mass = spring_constant / (2.0 * np.pi * bare) ** 2
    delta = mass - bare_mass
    rate = np.gradient(delta, time) if time.size > 1 else np.zeros_like(delta)

    return EvaporationSeries(
        time=time,
        frequency=frequency,
        mass=mass,
        added_mass=delta,
        evaporation_rate=rate,
        spring_constant=spring_constant,
        bare_frequency=bare,
    )


def load_evaporation_series(
    files: Sequence[str | Path],
    spring_constant: float | None = None,
    bare_frequency: float | None = None,
    recompute_peak: bool = False,
) -> EvaporationSeries:
    """Carga una serie de ``.nid`` de thermal tuning y arma la evaporación.

    Lee la frecuencia de resonancia y el instante de cada archivo, ordena por
    tiempo y calcula la masa y la tasa de evaporación.

    Args:
        files: Archivos ``.nid`` de thermal tuning (uno por instante).
        spring_constant: N/m. Por defecto, el del primer archivo (metadata).
        bare_frequency: Hz. Por defecto, la frecuencia máxima de la serie.
        recompute_peak: Si ``True``, recalcula ``f0`` del espectro en vez de
            usar el valor del instrumento.
    """
    from spmkit.core.io import load

    spectra: list[ThermalSpectrum] = [extract_thermal(load(f)) for f in files]
    spectra = [s for s in spectra if s.timestamp is not None]
    if not spectra:
        raise ValueError("Ningún archivo con marca de tiempo válida")
    spectra.sort(key=lambda s: s.timestamp)  # type: ignore[arg-type,return-value]

    t0 = spectra[0].timestamp
    times = np.array([(s.timestamp - t0).total_seconds() for s in spectra])  # type: ignore[operator]
    if recompute_peak:
        freqs = np.array([find_resonance(s.frequency, s.psd).f0 for s in spectra])
    else:
        freqs = np.array([s.f0 for s in spectra])

    k = spectra[0].spring_constant if spring_constant is None else spring_constant
    return track_evaporation(times, freqs, k, bare_frequency)
