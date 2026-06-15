"""Tests del módulo de análisis espectral (PSD, Hurst, fractal, correlación).

Todos los datos son SINTÉTICOS — no se usan archivos reales.
"""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import spectral
from spmkit.core.models import SPMChannel

# ---------------------------------------------------------------------------
# Helpers para generar datos sintéticos
# ---------------------------------------------------------------------------

_N = 128
_RANGE = 1e-6  # 1 µm


def _make_channel(data: np.ndarray) -> SPMChannel:
    """Envuelve un array 2D en un SPMChannel con rango 1 µm × 1 µm."""
    return SPMChannel(
        name="Z-Axis",
        data=data,
        unit="m",
        x_range=_RANGE,
        y_range=_RANGE,
    )


def _fbm_surface(n: int, h: float, rng: np.random.Generator) -> np.ndarray:
    """Genera una superficie fBm por síntesis espectral.

    En el dominio de frecuencias, el ruido blanco gaussiano se filtra por
    ``q^(−(1 + H))``, de modo que la PSD resultante escala como
    ``q^(−2(1+H))`` ≈ ``q^(−β)`` con ``β = 2H + 2``.

    Args:
        n: Tamaño de la malla (n × n).
        h: Exponente de Hurst deseado (0 < H < 1).
        rng: Generador de números aleatorios reproducible.

    Returns:
        Superficie 2D de forma ``(n, n)`` en unidades arbitrarias.
    """
    # Ruido blanco complejo en frecuencias
    noise = rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n))

    # Malla de frecuencias (centrada en 0)
    freq = np.fft.fftfreq(n)
    fx, fy = np.meshgrid(freq, freq)
    q = np.sqrt(fx**2 + fy**2)

    # Filtro espectral: q^(−(1+H)); evitar división por cero en q=0
    # np.errstate suprime el RuntimeWarning de 0**(-exp) que numpy evalúa antes del where
    with np.errstate(divide="ignore", invalid="ignore"):
        filt = np.where(q > 0, q ** (-(1.0 + h)), 0.0)

    # Superficie en espacio real
    surface_f = np.fft.ifft2(noise * filt)
    return surface_f.real


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRadialPSD:
    """Pruebas de la función radial_psd."""

    def test_psd_decae_con_frecuencia(self) -> None:
        """Para una superficie autoafín, la PSD debe decrecer con q."""
        rng = np.random.default_rng(0)
        z = _fbm_surface(_N, h=0.7, rng=rng)
        ch = _make_channel(z)
        rpsd = spectral.radial_psd(ch)

        assert rpsd.q.size > 2, "Deben existir al menos 3 bins radiales"
        # La PSD en el primer bin debe ser mayor que en el último
        assert (
            rpsd.psd[0] > rpsd.psd[-1]
        ), f"Se esperaba PSD decreciente; psd[0]={rpsd.psd[0]:.3e} psd[-1]={rpsd.psd[-1]:.3e}"

    def test_q_es_creciente(self) -> None:
        """Los valores de q deben ser estrictamente crecientes."""
        rng = np.random.default_rng(0)
        z = _fbm_surface(_N, h=0.7, rng=rng)
        ch = _make_channel(z)
        rpsd = spectral.radial_psd(ch)

        assert np.all(np.diff(rpsd.q) > 0), "q debe ser estrictamente creciente"

    def test_to_dict_contiene_claves(self) -> None:
        """to_dict debe contener las claves 'q', 'psd' y 'q_unit'."""
        rng = np.random.default_rng(1)
        z = rng.normal(0, 1, (_N, _N))
        ch = _make_channel(z)
        d = spectral.radial_psd(ch).to_dict()

        assert "q" in d
        assert "psd" in d
        assert "q_unit" in d
        assert isinstance(d["q"], list)
        assert isinstance(d["psd"], list)
        assert d["q_unit"] == "1/m"

    def test_q_en_unidades_correctas(self) -> None:
        """Los valores de q deben ser del orden de 1/x_range para el primer bin."""
        rng = np.random.default_rng(2)
        z = rng.normal(0, 1, (_N, _N))
        ch = _make_channel(z)
        rpsd = spectral.radial_psd(ch)

        # q mínimo esperado ≈ 1 / x_range = 1 / 1e-6 = 1e6 1/m
        q_expected_min = 1.0 / _RANGE
        assert rpsd.q[0] > 0, "q[0] debe ser positivo"
        # El primer bin debe estar cerca del mínimo teórico (tolerancia de 2 bins)
        assert rpsd.q[0] < 3 * q_expected_min, "q[0] demasiado grande para la escala"


class TestFractalDimension:
    """Pruebas de la función fractal_dimension."""

    def test_recupera_hurst_conocido(self) -> None:
        """Para una superficie fBm sintética con H=0.7, se recupera H dentro de ±0.2."""
        h_target = 0.7
        rng = np.random.default_rng(0)
        z = _fbm_surface(_N, h=h_target, rng=rng)
        ch = _make_channel(z)

        result = spectral.fractal_dimension(ch)

        assert (
            abs(result.hurst - h_target) < 0.2
        ), f"H recuperado={result.hurst:.3f} demasiado lejos de H_objetivo={h_target}"

    def test_dimension_fractal_en_rango(self) -> None:
        """D debe estar en [2, 3] para cualquier superficie SPM."""
        rng = np.random.default_rng(0)
        z = _fbm_surface(_N, h=0.7, rng=rng)
        ch = _make_channel(z)

        result = spectral.fractal_dimension(ch)

        assert (
            2.0 <= result.fractal_dimension <= 3.0
        ), f"D={result.fractal_dimension:.3f} fuera del rango [2, 3]"

    def test_hurst_en_rango(self) -> None:
        """H debe estar clipado a [0, 1]."""
        rng = np.random.default_rng(42)
        z = rng.normal(0, 1, (_N, _N))  # ruido blanco: H ≈ 0
        ch = _make_channel(z)

        result = spectral.fractal_dimension(ch)

        assert 0.0 <= result.hurst <= 1.0, f"H={result.hurst:.3f} fuera de [0, 1]"

    def test_relacion_d_y_h(self) -> None:
        """Debe cumplirse D = 3 - H."""
        rng = np.random.default_rng(0)
        z = _fbm_surface(_N, h=0.7, rng=rng)
        ch = _make_channel(z)

        result = spectral.fractal_dimension(ch)

        assert abs(result.fractal_dimension - (3.0 - result.hurst)) < 1e-10

    def test_to_dict_contiene_claves(self) -> None:
        """to_dict debe contener hurst, fractal_dimension, psd_slope, r_squared."""
        rng = np.random.default_rng(0)
        z = _fbm_surface(_N, h=0.5, rng=rng)
        ch = _make_channel(z)

        d = spectral.fractal_dimension(ch).to_dict()

        assert {"hurst", "fractal_dimension", "psd_slope", "r_squared"} == set(d.keys())

    def test_superficie_plana_no_falla(self) -> None:
        """Una superficie constante no debe lanzar excepción ni producir NaN."""
        z = np.full((_N, _N), 3.14)
        ch = _make_channel(z)

        result = spectral.fractal_dimension(ch)

        assert np.isfinite(result.hurst)
        assert np.isfinite(result.fractal_dimension)
        assert np.isfinite(result.psd_slope)
        assert np.isfinite(result.r_squared)
        assert 0.0 <= result.hurst <= 1.0
        assert 2.0 <= result.fractal_dimension <= 3.0

    def test_rango_q_personalizado(self) -> None:
        """Pasar q_min y q_max debe devolver un resultado finito."""
        rng = np.random.default_rng(0)
        z = _fbm_surface(_N, h=0.7, rng=rng)
        ch = _make_channel(z)
        rpsd = spectral.radial_psd(ch)
        q_mid = float(rpsd.q[len(rpsd.q) // 2])

        result = spectral.fractal_dimension(ch, q_min=rpsd.q[2], q_max=q_mid)

        assert np.isfinite(result.hurst)


class TestCorrelationLength:
    """Pruebas de la función correlation_length."""

    def test_superficie_plana_no_falla(self) -> None:
        """Una superficie constante no debe lanzar excepción ni producir NaN."""
        z = np.full((_N, _N), 1.0)
        ch = _make_channel(z)

        lc = spectral.correlation_length(ch)

        assert np.isfinite(lc)
        assert lc > 0.0

    def test_longitud_en_metros(self) -> None:
        """La longitud de correlación debe ser positiva y del orden del rango físico."""
        rng = np.random.default_rng(0)
        z = _fbm_surface(_N, h=0.7, rng=rng)
        ch = _make_channel(z)

        lc = spectral.correlation_length(ch)

        assert lc > 0.0, "La longitud de correlación debe ser positiva"
        # Debe ser menor que el tamaño total del barrido
        assert lc <= _RANGE, f"lc={lc:.3e} supera el rango físico {_RANGE:.3e} m"

    def test_ruido_blanco_correlacion_corta(self) -> None:
        """El ruido blanco tiene correlación muy corta (del orden del pixel_size)."""
        rng = np.random.default_rng(7)
        z = rng.normal(0, 1, (_N, _N))
        ch = _make_channel(z)

        lc = spectral.correlation_length(ch)
        pixel = ch.pixel_size_x

        # Para ruido blanco la correlación debe ser corta: < 10 píxeles
        assert (
            lc < 10 * pixel
        ), f"lc={lc:.3e} m demasiado larga para ruido blanco (pixel={pixel:.3e} m)"

    def test_superficie_correlacionada_longitud_mayor(self) -> None:
        """Una superficie muy suave (H≈1) debe tener mayor correlación que ruido blanco."""
        rng = np.random.default_rng(3)
        z_rough = rng.normal(0, 1, (_N, _N))
        z_smooth = _fbm_surface(_N, h=0.9, rng=rng)

        ch_rough = _make_channel(z_rough)
        ch_smooth = _make_channel(z_smooth)

        lc_rough = spectral.correlation_length(ch_rough)
        lc_smooth = spectral.correlation_length(ch_smooth)

        assert (
            lc_smooth > lc_rough
        ), f"Se esperaba lc_smooth={lc_smooth:.3e} > lc_rough={lc_rough:.3e}"


class TestIntegration:
    """Tests de integración entre funciones."""

    def test_pipeline_completo_fbm(self) -> None:
        """Pipeline completo: generar fBm → PSD → fractal → correlación sin error."""
        rng = np.random.default_rng(99)
        z = _fbm_surface(_N, h=0.6, rng=rng)
        ch = _make_channel(z)

        rpsd = spectral.radial_psd(ch)
        frac = spectral.fractal_dimension(ch)
        lc = spectral.correlation_length(ch)

        assert rpsd.q.size > 0
        assert np.isfinite(frac.hurst)
        assert np.isfinite(lc)
        assert 2.0 <= frac.fractal_dimension <= 3.0

    @pytest.mark.parametrize("h_target", [0.3, 0.5, 0.7])
    def test_dimension_fractal_parametrico(self, h_target: float) -> None:
        """Para distintos H, D y H deben estar en sus rangos válidos."""
        rng = np.random.default_rng(42)
        z = _fbm_surface(_N, h=h_target, rng=rng)
        ch = _make_channel(z)
        result = spectral.fractal_dimension(ch)

        assert 2.0 <= result.fractal_dimension <= 3.0
        assert 0.0 <= result.hurst <= 1.0
