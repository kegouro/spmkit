"""Resonancia del cantiléver y sensado de masa por desplazamiento de frecuencia.

Un cantiléver es un oscilador armónico: ``f0 = (1/2π)·√(k/m_eff)``. Al añadir
masa en la punta (p.ej. una masa añadida), ``f0`` baja; al evaporarse la
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
def effective_spring_constant(k_end: float, x_over_l: float = 1.0) -> float:
    """Constante de resorte efectiva en la posición de carga.

    La muestra se carga en una posición ``x`` a lo largo del
    cantiléver (medida en micrografías ópticas, como fracción ``x/L`` de la
    longitud). La constante efectiva en esa posición se relaciona con la del
    extremo ``k(L)`` (medida por el método de ruido térmico) por::

        k(x) = k(L) / (x/L)³

    Cargar más cerca de la base (``x/L`` < 1) endurece el resorte efectivo.
    """
    if not 0 < x_over_l <= 1:
        raise ValueError("x_over_l debe estar en (0, 1]")
    return k_end / (x_over_l**3)


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
    x_over_l: float = 1.0,
) -> EvaporationSeries:
    """Calcula masa, masa añadida y tasa de evaporación a partir de ``f(t)``.

    Usa la fórmula de sensado de masa por desplazamiento de frecuencia::

        Δm = k(x)/(4π²) · (1/f² − 1/f_desnuda²),   k(x) = k(L)/(x/L)³

    Args:
        time: Tiempos (s), preferiblemente relativos al primer punto.
        frequency: Resonancia en cada instante (Hz).
        spring_constant: Constante de resorte del **extremo** k(L) (N/m),
            típicamente medida por el método de ruido térmico.
        bare_frequency: Frecuencia del cantiléver desnudo (Hz). Por defecto, la
            frecuencia máxima de la serie (estado completamente evaporado).
        x_over_l: Posición relativa de carga ``x/L`` (de micrografías ópticas).
            ``1.0`` = en el extremo. Se usa para obtener ``k(x) = k(L)/(x/L)³``.
    """
    time = np.asarray(time, dtype=np.float64)
    frequency = np.asarray(frequency, dtype=np.float64)
    if time.size != frequency.size:
        raise ValueError("time y frequency deben tener el mismo tamaño")
    bare = float(np.max(frequency)) if bare_frequency is None else bare_frequency
    k_x = effective_spring_constant(spring_constant, x_over_l)

    mass = k_x / (2.0 * np.pi * frequency) ** 2
    bare_mass = k_x / (2.0 * np.pi * bare) ** 2
    delta = mass - bare_mass
    rate = np.gradient(delta, time) if time.size > 1 else np.zeros_like(delta)

    return EvaporationSeries(
        time=time,
        frequency=frequency,
        mass=mass,
        added_mass=delta,
        evaporation_rate=rate,
        spring_constant=k_x,
        bare_frequency=bare,
    )


def load_evaporation_series(
    files: Sequence[str | Path],
    spring_constant: float | None = None,
    bare_frequency: float | None = None,
    recompute_peak: bool = False,
    x_over_l: float = 1.0,
) -> EvaporationSeries:
    """Carga una serie de ``.nid`` de thermal tuning y arma la evaporación.

    Lee la frecuencia de resonancia y el instante de cada archivo, ordena por
    tiempo y calcula la masa y la tasa de evaporación.

    Args:
        files: Archivos ``.nid`` de thermal tuning (uno por instante).
        spring_constant: k(L) del extremo (N/m). Por defecto, el del primer
            archivo (metadata, método de ruido térmico).
        bare_frequency: Hz. Por defecto, la frecuencia máxima de la serie.
        recompute_peak: Si ``True``, recalcula ``f0`` del espectro en vez de
            usar el valor del instrumento.
        x_over_l: Posición relativa de carga ``x/L`` → ``k(x) = k(L)/(x/L)³``.
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
    return track_evaporation(times, freqs, k, bare_frequency, x_over_l=x_over_l)


# --------------------------------------------------------- análisis avanzado


def fit_sho(
    frequency: np.ndarray,
    psd: np.ndarray,
    f_min: float | None = None,
    f_max: float | None = None,
) -> ResonancePeak:
    """Ajusta el modelo SHO/Lorentziano al pico térmico.

    Modelo de densidad espectral de amplitud de un oscilador armónico térmico::

        ASD(f) = sqrt( A² · f0⁴ / ((f² - f0²)² + (f0·f/Q)²) ) + noise_floor

    Usa ``scipy.optimize.curve_fit`` para ajustar los parámetros
    ``(A, f0, Q, noise_floor)``.  Si scipy no está disponible o el ajuste
    falla, cae al detector de pico crudo :func:`find_resonance`.

    Args:
        frequency: Array de frecuencias (Hz).
        psd: Array de densidad espectral de amplitud (m/√Hz).
        f_min: Límite inferior del rango de ajuste (Hz).
        f_max: Límite superior del rango de ajuste (Hz).

    Returns:
        :class:`ResonancePeak` con f0 más preciso que el pico crudo.
    """
    frequency = np.asarray(frequency, dtype=np.float64)
    psd = np.asarray(psd, dtype=np.float64)

    mask = np.ones(frequency.size, dtype=bool)
    if f_min is not None:
        mask &= frequency >= f_min
    if f_max is not None:
        mask &= frequency <= f_max
    fr, pr = frequency[mask], psd[mask]
    if fr.size < 5:
        return find_resonance(frequency, psd, f_min, f_max)

    def _model(f: np.ndarray, A: float, f0: float, Q: float, noise: float) -> np.ndarray:
        denom = (f**2 - f0**2) ** 2 + (f0 * f / Q) ** 2
        return np.sqrt(np.maximum(A**2 * f0**4 / denom, 0.0)) + noise

    peak_idx = int(np.argmax(pr))
    f0_guess = float(fr[peak_idx])
    A_guess = float(pr[peak_idx])
    noise_guess = float(np.median(pr))
    p0 = [A_guess, f0_guess, 100.0, noise_guess]
    lower = [0.0, fr[0], 1.0, 0.0]
    upper = [A_guess * 100, fr[-1], 10_000.0, A_guess]

    try:
        from scipy.optimize import curve_fit  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "scipy es necesario para fit_sho. Instala con: pip install 'spmkit[grains]'"
        ) from exc

    try:
        popt, _ = curve_fit(_model, fr, pr, p0=p0, bounds=(lower, upper), maxfev=10_000)
        A_fit, f0_fit, Q_fit, _ = popt
        fwhm_fit = f0_fit / Q_fit
        return ResonancePeak(f0=f0_fit, q_factor=Q_fit, amplitude=A_fit, fwhm=fwhm_fit)
    except Exception:  # noqa: BLE001
        return find_resonance(frequency, psd, f_min, f_max)


def droplet_radius(added_mass: np.ndarray | float, density: float = 1000.0) -> np.ndarray | float:
    """Calcula el radio de la gota a partir de la masa añadida.

    Asume gota esférica de densidad ``density`` (kg/m³)::

        m = ρ · (4/3)π r³  →  r = (3m / (4πρ))^(1/3)

    Masas negativas o cero devuelven radio 0 (sin raíz cúbica de negativos).

    Args:
        added_mass: Masa añadida (kg), escalar o array.
        density: Densidad del líquido (kg/m³); por defecto agua = 1000.

    Returns:
        Radio (m), mismo tipo que la entrada.
    """
    scalar = np.ndim(added_mass) == 0
    m = np.atleast_1d(np.asarray(added_mass, dtype=np.float64))
    m_clip = np.clip(m, 0.0, None)
    r = np.where(m_clip > 0.0, (3.0 * m_clip / (4.0 * np.pi * density)) ** (1.0 / 3.0), 0.0)
    return float(r[0]) if scalar else r


@dataclass(frozen=True)
class D2LawResult:
    """Resultado del ajuste de la ley d² (evaporación limitada por difusión).

    La ley d² establece que el cuadrado del diámetro de una gota esférica
    decrece linealmente con el tiempo::

        d²(t) = d0² - K·t

    donde ``K = d0²/τ`` es la constante de evaporación (m²/s) y ``τ`` es el
    tiempo total de evaporación.  El ajuste se hace por regresión lineal de
    ``(2r)²`` frente a ``t``.
    """

    r0: float  # radio inicial (m)
    tau: float  # tiempo total de evaporación (s)
    rate_constant: float  # K = -d(d²)/dt  (m²/s)
    r_squared: float  # coeficiente de determinación del ajuste lineal
    is_diffusion_limited: bool  # True si r_squared > 0.95

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "r0_m": self.r0,
            "tau_s": self.tau,
            "rate_constant_m2_s": self.rate_constant,
            "r_squared": self.r_squared,
            "is_diffusion_limited": self.is_diffusion_limited,
        }


def fit_d2_law(time: np.ndarray, radius: np.ndarray | float) -> D2LawResult:
    """Ajusta la ley d² a una serie de radios de gota.

    La ley d² dice que el cuadrado del diámetro decrece linealmente::

        d²(t) = d0² - K·t

    equivalente a::

        (2r)²  = d0²  −  K · t

    Ajuste: regresión lineal (``np.polyfit`` grado 1) de ``d² = (2r)²``
    frente a ``t``, usando solo puntos donde ``radius > 0``.

    De la recta ``d² = b + a·t`` (``a < 0`` esperado)::

        d0² = b  (intercepto)
        K   = −a  (pendiente negada, m²/s)
        τ   = d0² / K  si K > 0, si no τ = ∞

    El coeficiente de determinación R² mide la bondad del ajuste lineal.
    Se considera evaporación limitada por difusión si R² > 0.95.

    Args:
        time: Tiempos (s).
        radius: Radio de la gota en cada instante (m).

    Returns:
        :class:`D2LawResult` con r0, τ, K, R² e indicador de difusión.
    """
    time = np.asarray(time, dtype=np.float64)
    radius = np.asarray(radius, dtype=np.float64)

    mask = radius > 0
    if mask.sum() < 2:
        return D2LawResult(
            r0=0.0, tau=float("inf"), rate_constant=0.0, r_squared=0.0, is_diffusion_limited=False
        )

    t_fit = time[mask]
    d2 = (2.0 * radius[mask]) ** 2  # diámetro al cuadrado (m²)

    # Ajuste lineal: d² = b + a·t
    coeffs = np.polyfit(t_fit, d2, 1)
    a, b = float(coeffs[0]), float(coeffs[1])

    d2_pred = a * t_fit + b
    ss_res = float(np.sum((d2 - d2_pred) ** 2))
    ss_tot = float(np.sum((d2 - np.mean(d2)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

    d0_sq = b  # intercepto = d² inicial
    K = -a  # constante de evaporación (m²/s); debería ser > 0
    tau = d0_sq / K if K > 0 else float("inf")
    r0 = float(np.sqrt(max(d0_sq, 0.0)) / 2.0)

    return D2LawResult(
        r0=r0,
        tau=tau,
        rate_constant=K,
        r_squared=r2,
        is_diffusion_limited=r2 > 0.95,
    )


def animate_evaporation(
    spectra: list[ThermalSpectrum],
    path: str | Path,
    fps: int = 4,
) -> Path:
    """Crea un GIF animando los espectros PSD de la serie de evaporación.

    Cada frame muestra el espectro PSD (ASD vs frecuencia) de un instante,
    con un título que indica el tiempo o el índice.

    Usa ``matplotlib.animation.FuncAnimation`` y guarda con ``writer="pillow"``.

    Args:
        spectra: Lista de :class:`ThermalSpectrum`, uno por instante.
        path: Ruta de salida del GIF.
        fps: Fotogramas por segundo.

    Returns:
        :class:`pathlib.Path` apuntando al GIF generado.
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from matplotlib.animation import FuncAnimation  # noqa: PLC0415

    out = Path(path)
    if not spectra:
        raise ValueError("La lista de espectros está vacía")

    fig, ax = plt.subplots(figsize=(7, 4))
    t0 = spectra[0].timestamp

    fr0 = spectra[0].frequency
    pr0 = spectra[0].psd
    (line,) = ax.plot(fr0 / 1e3, pr0 * 1e12, color="#2dd4bf", lw=1.2)
    ax.set_xlabel("Frecuencia (kHz)")
    ax.set_ylabel("ASD (pm/√Hz)")
    title_obj = ax.set_title("")
    ax.set_xlim(float(fr0[0]) / 1e3, float(fr0[-1]) / 1e3)
    all_psd = np.concatenate([s.psd for s in spectra])
    ax.set_ylim(0, float(np.nanmax(all_psd)) * 1e12 * 1.05)
    fig.tight_layout()

    def _update(i: int) -> tuple:
        sp = spectra[i]
        line.set_data(sp.frequency / 1e3, sp.psd * 1e12)
        if t0 is not None and sp.timestamp is not None:
            dt = (sp.timestamp - t0).total_seconds()
            label = f"t = {dt / 3600:.2f} h  (frame {i + 1}/{len(spectra)})"
        else:
            label = f"Frame {i + 1}/{len(spectra)}"
        title_obj.set_text(label)
        return line, title_obj

    ani = FuncAnimation(fig, _update, frames=len(spectra), blit=True)
    ani.save(str(out), writer="pillow", fps=fps)
    plt.close(fig)
    return out
