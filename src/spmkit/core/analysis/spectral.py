"""Análisis espectral de superficies SPM: PSD radial, exponente de Hurst y dimensión fractal.

Las funciones esperan datos **ya nivelados** (ver :mod:`spmkit.core.analysis.leveling`).

Referencias:
    - Jacobs, T.D.B. et al. (2017). The effect of atomic-scale roughness on the adhesion of
      nanoscale asperities. Tribology Letters, 65(3), 103.
    - Palasantzas, G. (1993). Roughness spectrum and surface width of self-affine fractal
      surfaces via the K-correlation model. Phys. Rev. B, 48(19), 14472.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spmkit.core.models import SPMChannel

# Umbral 1/e para la longitud de correlación
_INV_E: float = 1.0 / np.e


# ---------------------------------------------------------------------------
# Dataclasses de resultados
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RadialPSD:
    """PSD radialmente promediada de una superficie SPM.

    Attributes:
        q: Vector de frecuencias espaciales (1/m), una por bin radial.
        psd: Densidad espectral de potencia promediada por bin (m²·m²).
        q_unit: Unidad de ``q`` (siempre ``"1/m"``).
    """

    q: np.ndarray
    psd: np.ndarray
    q_unit: str = "1/m"

    def to_dict(self) -> dict:
        """Devuelve los campos como diccionario (arrays → listas)."""
        return {
            "q": self.q.tolist(),
            "psd": self.psd.tolist(),
            "q_unit": self.q_unit,
        }


@dataclass(frozen=True)
class FractalResult:
    """Resultado del análisis fractal / de Hurst via PSD.

    Attributes:
        hurst: Exponente de Hurst H ∈ [0, 1].
        fractal_dimension: Dimensión fractal D = 3 − H ∈ [2, 3].
        psd_slope: Exponente β de la ley de potencia P(q) ∝ q^(−β).
        r_squared: Coeficiente de determinación R² del ajuste log-log.
    """

    hurst: float
    fractal_dimension: float
    psd_slope: float
    r_squared: float

    def to_dict(self) -> dict:
        """Devuelve los campos como diccionario."""
        return {
            "hurst": self.hurst,
            "fractal_dimension": self.fractal_dimension,
            "psd_slope": self.psd_slope,
            "r_squared": self.r_squared,
        }


# ---------------------------------------------------------------------------
# Funciones de análisis
# ---------------------------------------------------------------------------


def radial_psd(channel: SPMChannel) -> RadialPSD:
    """Calcula la PSD 2D y la promedia en anillos radiales.

    La PSD 2D se calcula como:

    .. math::

        P(q_x, q_y) = \\frac{|\\hat{F}(q_x, q_y)|^2 \\cdot dx \\cdot dy}{N_x \\cdot N_y}

    donde ``\\hat{F}`` es la DFT 2D de ``z − ⟨z⟩``.

    Args:
        channel: Canal SPM con datos ya nivelados.

    Returns:
        :class:`RadialPSD` con los vectores ``q`` (1/m) y ``psd`` (promedio por bin).
    """
    z = np.asarray(channel.data, dtype=np.float64)
    ny, nx = z.shape
    dx = channel.pixel_size_x
    dy = channel.pixel_size_y

    # FFT 2D y PSD normalizada (densidad espectral de potencia)
    f_hat = np.fft.fft2(z - z.mean())
    psd2d = (np.abs(np.fft.fftshift(f_hat)) ** 2) * (dx * dy) / (nx * ny)

    # Malla de frecuencias espaciales
    qx = np.fft.fftshift(np.fft.fftfreq(nx, d=dx))  # 1/m
    qy = np.fft.fftshift(np.fft.fftfreq(ny, d=dy))  # 1/m
    qx_grid, qy_grid = np.meshgrid(qx, qy)
    q_mod = np.sqrt(qx_grid**2 + qy_grid**2)  # módulo radial

    # Promedio radial en bins
    q_max = float(q_mod.max())
    n_bins = min(ny, nx) // 2
    bin_edges = np.linspace(0.0, q_max, n_bins + 1)

    q_centers: list[float] = []
    psd_mean: list[float] = []

    for i in range(n_bins):
        q_lo = bin_edges[i]
        q_hi = bin_edges[i + 1]
        # El primer bin comienza en q>0 para excluir la componente DC
        mask = (q_mod > 0) & (q_mod <= q_hi) if i == 0 else (q_mod > q_lo) & (q_mod <= q_hi)
        if not mask.any():
            continue
        q_centers.append(float(0.5 * (q_lo + q_hi)))
        psd_mean.append(float(psd2d[mask].mean()))

    q_arr = np.asarray(q_centers, dtype=np.float64)
    psd_arr = np.asarray(psd_mean, dtype=np.float64)

    return RadialPSD(q=q_arr, psd=psd_arr)


def fractal_dimension(
    channel: SPMChannel,
    q_min: float | None = None,
    q_max: float | None = None,
) -> FractalResult:
    """Estima el exponente de Hurst y la dimensión fractal desde la PSD radial.

    Para una superficie autoafín la PSD radial escala como:

    .. math::

        P(q) \\propto q^{-\\beta}, \\quad \\beta = 2H + 2

    El ajuste se realiza por regresión lineal sobre ``log₁₀(P)`` vs ``log₁₀(q)``.

    Args:
        channel: Canal SPM con datos ya nivelados.
        q_min: Frecuencia mínima del rango de ajuste (1/m). Si es ``None``
               se usa el mínimo q > 0 con P > 0.
        q_max: Frecuencia máxima del rango de ajuste (1/m). Si es ``None``
               se usa el máximo disponible.

    Returns:
        :class:`FractalResult` con H, D, β y R².
    """
    rpsd = radial_psd(channel)
    q = rpsd.q
    psd = rpsd.psd

    # Filtro: solo q > 0 y PSD > 0
    valid = (q > 0) & (psd > 0)
    if q_min is not None:
        valid &= q >= q_min
    if q_max is not None:
        valid &= q <= q_max

    # Caso degenerado: superficie plana u homogénea
    if valid.sum() < 2:
        return FractalResult(hurst=0.5, fractal_dimension=2.5, psd_slope=3.0, r_squared=0.0)

    log_q = np.log10(q[valid])
    log_p = np.log10(psd[valid])

    # Regresión lineal: log_p = slope * log_q + intercept
    coeffs = np.polyfit(log_q, log_p, 1)
    slope = float(coeffs[0])

    # β = −pendiente  (la pendiente debe ser negativa para autoafinidad)
    beta = -slope

    # Exponente de Hurst: β = 2H + 2  →  H = (β − 2) / 2
    h_raw = (beta - 2.0) / 2.0
    hurst = float(np.clip(h_raw, 0.0, 1.0))

    # Dimensión fractal (superficie 2D embebida en 3D)
    d_fractal = 3.0 - hurst

    # R² del ajuste en escala log-log
    log_p_fit = np.polyval(coeffs, log_q)
    ss_res = float(np.sum((log_p - log_p_fit) ** 2))
    ss_tot = float(np.sum((log_p - log_p.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0

    return FractalResult(
        hurst=hurst,
        fractal_dimension=d_fractal,
        psd_slope=beta,
        r_squared=r_squared,
    )


def correlation_length(channel: SPMChannel) -> float:
    """Calcula la longitud de correlación lateral desde la función de autocorrelación 2D.

    La autocorrelación se obtiene via FFT (teorema de Wiener-Khinchin):

    .. math::

        C(r_x, r_y) = \\mathcal{F}^{-1}\\{|\\mathcal{F}\\{z - \\langle z \\rangle\\}|^2\\}

    Se normaliza de modo que C(0,0) = 1, se aplica ``fftshift`` para centrar
    el origen y se toma el perfil radial promedio. La longitud de correlación
    es el primer lag radial donde C cae por debajo de 1/e ≈ 0.3679.

    Si la función de autocorrelación no cruza ese umbral, se devuelve el lag
    máximo disponible (superficie altamente correlacionada).

    Args:
        channel: Canal SPM con datos ya nivelados.

    Returns:
        Longitud de correlación en metros.
    """
    z = np.asarray(channel.data, dtype=np.float64)
    ny, nx = z.shape
    dx = channel.pixel_size_x
    dy = channel.pixel_size_y

    # Autocorrelación 2D normalizada via FFT
    f_hat = np.fft.fft2(z - z.mean())
    acf2d_raw = np.fft.ifft2(np.abs(f_hat) ** 2).real
    acf2d_shifted = np.fft.fftshift(acf2d_raw)

    # Normalizar por el valor en el origen (varianza × N²)
    origin_val = float(acf2d_shifted[ny // 2, nx // 2])
    if origin_val <= 0.0:
        # Superficie plana: longitud de correlación indefinida → devuelve max lag
        return float(min(channel.x_range, channel.y_range) / 2.0)

    acf_norm = acf2d_shifted / origin_val

    # Malla de lags en metros
    lags_x = (np.arange(nx) - nx // 2) * dx
    lags_y = (np.arange(ny) - ny // 2) * dy
    lx_grid, ly_grid = np.meshgrid(lags_x, lags_y)
    r_mod = np.sqrt(lx_grid**2 + ly_grid**2)

    # Perfil radial promedio del ACF
    r_max = float(r_mod.max())
    n_bins = min(ny, nx) // 2
    bin_edges = np.linspace(0.0, r_max, n_bins + 1)

    r_centers: list[float] = []
    acf_mean: list[float] = []

    for i in range(n_bins):
        r_lo = bin_edges[i]
        r_hi = bin_edges[i + 1]
        mask = r_mod <= r_hi if i == 0 else (r_mod > r_lo) & (r_mod <= r_hi)
        if not mask.any():
            continue
        r_centers.append(float(0.5 * (r_lo + r_hi)))
        acf_mean.append(float(acf_norm[mask].mean()))

    if not r_centers:
        return float(min(channel.x_range, channel.y_range) / 2.0)

    r_arr = np.asarray(r_centers, dtype=np.float64)
    acf_arr = np.asarray(acf_mean, dtype=np.float64)

    # Buscar el primer cruce por debajo de 1/e
    below = np.where(acf_arr < _INV_E)[0]
    if below.size == 0:
        # No cruza → devuelve lag máximo disponible
        return float(r_arr[-1])

    idx = int(below[0])
    if idx == 0:
        # El ACF ya empieza por debajo de 1/e (superficie muy rugosa / sin correlación)
        return float(r_arr[0])

    # Interpolación lineal entre el bin anterior y el actual para mayor precisión
    r0, a0 = r_arr[idx - 1], acf_arr[idx - 1]
    r1, a1 = r_arr[idx], acf_arr[idx]
    r_corr = r0 + (r1 - r0) * (_INV_E - a0) / (a1 - a0) if a0 != a1 else float(r1)

    return float(r_corr)
