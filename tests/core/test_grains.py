"""Tests de detección de granos/partículas (datos sintéticos)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from spmkit.core.analysis import grains
from spmkit.core.models import SPMChannel

# Tamaño de píxel físico utilizado en todos los canales sintéticos: 10 nm/píxel.
_PIXEL_NM = 10e-9  # m
_GRID = 64  # píxeles por lado
_RANGE = _GRID * _PIXEL_NM  # metros


def _make_channel(data: np.ndarray) -> SPMChannel:
    """Crea un SPMChannel con escala conocida a partir de un array 2D."""
    return SPMChannel(
        name="Z-Axis",
        data=data,
        unit="m",
        x_range=_RANGE,
        y_range=_RANGE,
    )


def _gaussian_blob(
    rows: int,
    cols: int,
    cy: float,
    cx: float,
    sigma: float,
    amplitude: float,
) -> np.ndarray:
    """Genera un blob gaussiano 2D centrado en (cy, cx) con radio sigma."""
    yy, xx = np.mgrid[0:rows, 0:cols]
    return amplitude * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma**2))


def _synthetic_grains(n: int = 5, sigma: float = 3.0, amplitude: float = 1.0) -> SPMChannel:
    """Genera una imagen con *n* granos gaussianos distribuidos en rejilla."""
    data = np.zeros((_GRID, _GRID), dtype=np.float64)
    step = _GRID // (int(math.ceil(math.sqrt(n))) + 1)
    positions: list[tuple[float, float]] = []
    r, c = step, step
    for _ in range(n):
        data += _gaussian_blob(_GRID, _GRID, r, c, sigma, amplitude)
        positions.append((r, c))
        c += step
        if c >= _GRID - step:
            c = step
            r += step
    return _make_channel(data)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def flat_zero() -> SPMChannel:
    """Superficie plana (todos ceros). No debe detectarse ningún grano."""
    return _make_channel(np.zeros((_GRID, _GRID), dtype=np.float64))


@pytest.fixture
def five_grains() -> SPMChannel:
    """Imagen con 5 granos gaussianos claramente separados."""
    return _synthetic_grains(n=5, sigma=3.0, amplitude=2.0)


@pytest.fixture
def single_grain() -> SPMChannel:
    """Un único grano gaussiano en el centro."""
    data = _gaussian_blob(_GRID, _GRID, _GRID // 2, _GRID // 2, sigma=4.0, amplitude=1.5)
    return _make_channel(data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFlatImage:
    """Una imagen completamente plana no debe producir ningún grano."""

    def test_no_grains_detected(self, flat_zero: SPMChannel) -> None:
        result = grains.detect(flat_zero, threshold=0.5)
        assert result.n_grains == 0

    def test_coverage_is_zero(self, flat_zero: SPMChannel) -> None:
        result = grains.detect(flat_zero, threshold=0.5)
        assert result.coverage == pytest.approx(0.0)

    def test_arrays_are_empty(self, flat_zero: SPMChannel) -> None:
        result = grains.detect(flat_zero, threshold=0.5)
        assert result.areas.size == 0
        assert result.equivalent_diameters.size == 0
        assert result.mean_height.size == 0


class TestGrainCount:
    """El número de granos detectados debe ser cercano al número sintético."""

    def test_five_grains_found(self, five_grains: SPMChannel) -> None:
        # Con threshold automático y relative_height=0.5 deben encontrarse los 5.
        result = grains.detect(five_grains)
        assert result.n_grains == 5

    def test_single_grain_found(self, single_grain: SPMChannel) -> None:
        result = grains.detect(single_grain)
        assert result.n_grains == 1

    def test_explicit_threshold_filters_grains(self, five_grains: SPMChannel) -> None:
        # Con un umbral muy alto (superior al máximo) no debe haber granos.
        result = grains.detect(five_grains, threshold=999.0)
        assert result.n_grains == 0


class TestPhysicalMagnitudes:
    """Las magnitudes físicas deben ser coherentes y estar en el rango esperado."""

    def test_coverage_between_zero_and_one(self, five_grains: SPMChannel) -> None:
        result = grains.detect(five_grains)
        assert 0.0 < result.coverage < 1.0

    def test_areas_positive(self, five_grains: SPMChannel) -> None:
        result = grains.detect(five_grains)
        assert np.all(result.areas > 0.0)

    def test_diameters_positive(self, five_grains: SPMChannel) -> None:
        result = grains.detect(five_grains)
        assert np.all(result.equivalent_diameters > 0.0)

    def test_diameters_consistent_with_areas(self, five_grains: SPMChannel) -> None:
        """El diámetro equivalente debe ser 2*sqrt(area/pi)."""
        result = grains.detect(five_grains)
        expected = 2.0 * np.sqrt(result.areas / math.pi)
        np.testing.assert_allclose(result.equivalent_diameters, expected, rtol=1e-10)

    def test_mean_height_positive(self, five_grains: SPMChannel) -> None:
        result = grains.detect(five_grains)
        # Los granos tienen amplitud positiva, así que la altura media es > threshold
        assert np.all(result.mean_height > 0.0)

    def test_mean_diameter_is_mean_of_diameters(self, five_grains: SPMChannel) -> None:
        result = grains.detect(five_grains)
        assert result.mean_diameter == pytest.approx(float(np.mean(result.equivalent_diameters)))

    def test_density_positive(self, five_grains: SPMChannel) -> None:
        result = grains.detect(five_grains)
        assert result.density > 0.0

    def test_grain_diameter_in_nanometer_range(self, single_grain: SPMChannel) -> None:
        """El diámetro de un grano con sigma=4 píx * 10 nm/píx debe ser decenas de nm."""
        result = grains.detect(single_grain)
        diameter_nm = result.mean_diameter * 1e9
        # Un blob gaussiano con sigma=4 px → diámetro ~ 2..3 * sigma * pixel_size ≈ 80-120 nm
        assert 20.0 < diameter_nm < 500.0


class TestMinSize:
    """El parámetro min_size debe filtrar granos pequeños."""

    def test_min_size_removes_small_blobs(self) -> None:
        # Un único píxel elevado + un grano real
        data = np.zeros((_GRID, _GRID), dtype=np.float64)
        # Grano real: blob de radio 4 px
        data += _gaussian_blob(_GRID, _GRID, 32, 32, sigma=4.0, amplitude=2.0)
        # Ruido aislado: 1 píxel en una esquina
        data[0, 0] = 3.0  # valor alto pero 1 solo píxel
        ch = _make_channel(data)
        # Con min_size=4 el píxel aislado se descarta
        result_strict = grains.detect(ch, min_size=4)
        # Con min_size=1 lo incluye
        result_loose = grains.detect(ch, min_size=1)
        assert result_strict.n_grains <= result_loose.n_grains


class TestGrainResult:
    """Comprueba la interfaz pública de GrainResult."""

    def test_to_dict_keys(self, five_grains: SPMChannel) -> None:
        result = grains.detect(five_grains)
        d = result.to_dict()
        expected_keys = {
            "n_grains",
            "areas",
            "equivalent_diameters",
            "mean_height",
            "coverage",
            "unit_length",
            "mean_diameter",
            "density_per_um2",
        }
        assert expected_keys <= set(d)

    def test_to_dict_arrays_are_lists(self, five_grains: SPMChannel) -> None:
        d = grains.detect(five_grains).to_dict()
        assert isinstance(d["areas"], list)
        assert isinstance(d["equivalent_diameters"], list)
        assert isinstance(d["mean_height"], list)

    def test_labels_shape_matches_data(self, five_grains: SPMChannel) -> None:
        result = grains.detect(five_grains)
        assert result.labels.shape == five_grains.data.shape

    def test_labels_range(self, five_grains: SPMChannel) -> None:
        result = grains.detect(five_grains)
        assert int(result.labels.min()) == 0
        assert int(result.labels.max()) == result.n_grains

    def test_unit_length_matches_channel(self, five_grains: SPMChannel) -> None:
        result = grains.detect(five_grains)
        assert result.unit_length == five_grains.unit


class TestRelativeHeight:
    """Verifica el umbral automático basado en relative_height."""

    def test_high_relative_height_detects_fewer_grains(self) -> None:
        ch = _synthetic_grains(n=5, sigma=3.0, amplitude=2.0)
        result_low = grains.detect(ch, relative_height=0.1)
        result_high = grains.detect(ch, relative_height=0.95)
        # Con umbral muy alto se detectan menos (o iguales) granos
        assert result_high.n_grains <= result_low.n_grains

    def test_invalid_relative_height_raises(self, five_grains: SPMChannel) -> None:
        with pytest.raises(ValueError, match="relative_height"):
            grains.detect(five_grains, relative_height=0.0)

    def test_relative_height_one_is_valid(self, five_grains: SPMChannel) -> None:
        # 1.0 es límite superior válido (umbral = max → 0 granos es OK)
        result = grains.detect(five_grains, relative_height=1.0)
        assert isinstance(result, grains.GrainResult)
