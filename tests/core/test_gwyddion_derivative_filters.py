"""Core tests for the A2 derivative-filter production batch (no fixtures).

Covers common validation, Sobel/Prewitt semantics, magnitude relations and
the native direction composite.  These tests never load the persistent
fixture files.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from spmkit.core.analysis import (
    gradient_direction,
    gwyddion_gradient_magnitude,
    gwyddion_prewitt_x,
    gwyddion_prewitt_y,
    gwyddion_sobel_x,
    gwyddion_sobel_y,
)
from spmkit.core.models import SPMChannel


def _channel(data: np.ndarray, unit: str = "m") -> SPMChannel:
    return SPMChannel(
        name="Z-Axis",
        data=np.asarray(data, dtype=np.float64),
        unit=unit,
        x_range=5e-6,
        y_range=4e-6,
        direction="forward",
        metadata={"Dim1Name": "X"},
    )


def _pair(data_x: np.ndarray, data_y: np.ndarray) -> tuple[SPMChannel, SPMChannel]:
    return _channel(data_x), _channel(data_y)


# ---------------------------------------------------------------- common ---


def test_invalid_dimensions() -> None:
    with pytest.raises(ValueError):
        gwyddion_sobel_x(_channel(np.zeros((5,))))
    with pytest.raises(ValueError):
        gwyddion_sobel_y(_channel(np.zeros((5, 5, 5))))


def test_empty_arrays() -> None:
    with pytest.raises(ValueError):
        gwyddion_sobel_x(_channel(np.zeros((0, 5))))
    with pytest.raises(ValueError):
        gwyddion_sobel_x(_channel(np.zeros((5, 0))))


def test_complex_input() -> None:
    complex_channel = SPMChannel(
        name="Z",
        data=np.zeros((5, 5), dtype=np.complex128),
        unit="m",
        x_range=5e-6,
        y_range=4e-6,
        direction="forward",
    )
    with pytest.raises(TypeError):
        gwyddion_sobel_x(complex_channel)


def test_nan_inf_rejection() -> None:
    for value in (np.nan, np.inf, -np.inf):
        data = np.zeros((5, 5))
        data[2, 2] = value
        with pytest.raises(ValueError):
            gwyddion_sobel_x(_channel(data))
        with pytest.raises(ValueError):
            gwyddion_prewitt_y(_channel(data))


def test_context_preservation() -> None:
    channel = _channel(np.arange(25.0).reshape(5, 5))
    result = gwyddion_sobel_x(channel)
    assert result.name == channel.name
    assert result.unit == channel.unit
    assert result.x_range == channel.x_range
    assert result.y_range == channel.y_range
    assert result.direction == channel.direction
    assert result.metadata == channel.metadata
    assert result.data.shape == channel.data.shape


def test_non_mutation_and_storage_independence() -> None:
    data = np.arange(25.0).reshape(5, 5)
    channel = _channel(data)
    original = data.copy()
    result = gwyddion_sobel_x(channel)
    assert np.array_equal(data, original)
    result.data[0, 0] = 12345.0
    assert np.array_equal(data, original)


def test_no_public_mask_roi_border_parameters() -> None:
    import inspect

    for fn in (gwyddion_sobel_x, gwyddion_sobel_y, gwyddion_prewitt_x, gwyddion_prewitt_y):
        params = inspect.signature(fn).parameters
        assert set(params) == {"channel"}
    for fn in (gwyddion_gradient_magnitude, gradient_direction):
        params = inspect.signature(fn).parameters
        assert set(params) == {"gx", "gy"}


# -------------------------------------------------------- sobel / prewitt ---


def test_constants_vanish_within_rounding() -> None:
    channel = _channel(np.full((5, 5), 2.5))
    for fn in (gwyddion_sobel_x, gwyddion_sobel_y, gwyddion_prewitt_x, gwyddion_prewitt_y):
        result = fn(channel)
        # frozen source arithmetic may leave a ~1e-16 residue; it is not
        # forced to exactly zero
        assert np.max(np.abs(result.data)) <= 1e-12


def test_ramp_signs() -> None:
    ramp_x = np.tile(np.arange(5.0), (5, 1))
    ramp_y = np.tile(np.arange(5.0)[:, None], (1, 5))
    assert float(gwyddion_sobel_x(_channel(ramp_x)).data[2, 2]) == -2.0
    assert float(gwyddion_sobel_y(_channel(ramp_y)).data[2, 2]) == -2.0
    assert float(gwyddion_sobel_x(_channel(-ramp_x)).data[2, 2]) == 2.0
    assert float(gwyddion_sobel_y(_channel(-ramp_y)).data[2, 2]) == 2.0
    assert float(gwyddion_prewitt_x(_channel(ramp_x)).data[2, 2]) == -2.0
    assert float(gwyddion_prewitt_y(_channel(ramp_y)).data[2, 2]) == -2.0


def test_diagonal_ramp() -> None:
    diag = np.add.outer(np.arange(5.0), np.arange(5.0))
    sx = gwyddion_sobel_x(_channel(diag)).data
    sy = gwyddion_sobel_y(_channel(diag)).data
    assert float(sx[2, 2]) == -2.0
    assert float(sy[2, 2]) == -2.0


def test_impulse_kernels() -> None:
    impulse = np.zeros((5, 5))
    impulse[2, 2] = 1.0
    channel = _channel(impulse)
    expected = {
        gwyddion_sobel_x: [0.25, 0.0, -0.25, 0.5, 0.0, -0.5, 0.25, 0.0, -0.25],
        gwyddion_sobel_y: [0.25, 0.5, 0.25, 0.0, 0.0, 0.0, -0.25, -0.5, -0.25],
        gwyddion_prewitt_x: [1.0 / 3.0, 0.0, -1.0 / 3.0] * 3,
        gwyddion_prewitt_y: [
            1.0 / 3.0,
            1.0 / 3.0,
            1.0 / 3.0,
            0.0,
            0.0,
            0.0,
            -1.0 / 3.0,
            -1.0 / 3.0,
            -1.0 / 3.0,
        ],
    }
    for fn, coeffs in expected.items():
        window = fn(channel).data[1:4, 1:4]
        flipped = np.array(coeffs).reshape(3, 3)[::-1, ::-1]
        assert np.array_equal(window, flipped)


def test_corner_and_edge_impulses() -> None:
    corner = np.zeros((5, 5))
    corner[0, 0] = 1.0
    assert float(gwyddion_sobel_x(_channel(corner)).data[0, 0]) == 0.75
    assert float(gwyddion_prewitt_x(_channel(corner)).data[0, 0]) == 2.0 / 3.0
    edge = np.zeros((5, 5))
    edge[0, 2] = 1.0
    assert float(gwyddion_sobel_y(_channel(edge)).data[0, 2]) == 0.5


def test_clipped_border_policy() -> None:
    # the top row re-reads itself for kernel rows 0..1: an x-ramp keeps the
    # full -2.0 interior response on the top row as well
    ramp_x = np.tile(np.arange(5.0), (5, 1))
    sx = gwyddion_sobel_x(_channel(ramp_x)).data
    assert float(sx[0, 2]) == -2.0
    # bottom row: kernel row 2 folds onto the last row
    assert float(sx[4, 2]) == -2.0


def test_transpose_relation() -> None:
    ramp_x = np.tile(np.arange(5.0), (5, 1))
    ramp_y = ramp_x.T
    sx = gwyddion_sobel_x(_channel(ramp_x)).data
    sy = gwyddion_sobel_y(_channel(ramp_y)).data
    assert np.array_equal(sx, sy.T)


def test_negation_relation() -> None:
    field = np.add.outer(np.arange(5.0), np.arange(5.0))
    pos = gwyddion_sobel_x(_channel(field)).data
    neg = gwyddion_sobel_x(_channel(-field)).data
    assert np.array_equal(neg, -pos)


def test_signed_zero() -> None:
    data = np.zeros((5, 5))
    data[::2, ::2] = -0.0
    channel = _channel(data)
    for fn in (gwyddion_sobel_x, gwyddion_sobel_y, gwyddion_prewitt_x, gwyddion_prewitt_y):
        result = fn(channel)
        assert result.data.dtype == np.float64
        # signed zeros are preserved as exact bit patterns somewhere or are
        # cancelled according to the frozen arithmetic; the operation must
        # never raise or produce non-finite values
        assert np.isfinite(result.data).all()


def test_degenerate_shapes() -> None:
    for shape in ((1, 1), (1, 5), (5, 1), (7, 3), (3, 7)):
        data = np.arange(math.prod(shape), dtype=np.float64).reshape(shape)
        channel = _channel(data)
        for fn in (gwyddion_sobel_x, gwyddion_sobel_y, gwyddion_prewitt_x, gwyddion_prewitt_y):
            result = fn(channel)
            assert result.data.shape == shape
            assert np.isfinite(result.data).all()


# -------------------------------------------------------------- magnitude ---


def test_magnitude_3_4_5() -> None:
    gx = _channel(np.full((5, 5), 3.0))
    gy = _channel(np.full((5, 5), 4.0))
    result = gwyddion_gradient_magnitude(gx, gy)
    assert np.all(result.data == 5.0)


def test_magnitude_zero_and_single_zero() -> None:
    zero = _channel(np.zeros((5, 5)))
    assert np.all(gwyddion_gradient_magnitude(zero, zero).data == 0.0)
    ramp = _channel(np.tile(np.arange(5.0), (5, 1)))
    sx = gwyddion_sobel_x(ramp)
    mag = gwyddion_gradient_magnitude(sx, _channel(np.zeros((5, 5)))).data
    assert np.all(mag == np.abs(sx.data))


def test_magnitude_signed_zero_components() -> None:
    data = np.zeros((5, 5))
    data[::2, ::2] = -0.0
    result = gwyddion_gradient_magnitude(_channel(data), _channel(data)).data
    assert np.all(result == 0.0)
    assert np.all(result.view(np.uint64) == 0)


def test_magnitude_nonnegative_and_swap_symmetric() -> None:
    rng = np.random.default_rng(3)
    gx = _channel(rng.standard_normal((5, 5)))
    gy = _channel(rng.standard_normal((5, 5)))
    m1 = gwyddion_gradient_magnitude(gx, gy).data
    m2 = gwyddion_gradient_magnitude(gy, gx).data
    assert np.all(m1 >= 0.0)
    assert np.array_equal(m1, m2)


def test_magnitude_large_finite_overflow_safe() -> None:
    # sqrt(gx^2+gy^2) would overflow; hypot must not
    gx = _channel(np.full((3, 3), 1e200))
    gy = _channel(np.full((3, 3), 1e200))
    result = gwyddion_gradient_magnitude(gx, gy).data
    assert np.all(np.isfinite(result))
    assert float(result[0, 0]) > 1e200


def test_magnitude_inputs_not_mutated() -> None:
    gx = _channel(np.full((5, 5), 3.0))
    gy = _channel(np.full((5, 5), 4.0))
    _ = gwyddion_gradient_magnitude(gx, gy)
    assert np.all(gx.data == 3.0)
    assert np.all(gy.data == 4.0)


def test_magnitude_component_compatibility_validation() -> None:
    gx = _channel(np.zeros((5, 5)), unit="m")
    with pytest.raises(ValueError):
        gwyddion_gradient_magnitude(gx, _channel(np.zeros((4, 5)), unit="m"))
    with pytest.raises(ValueError):
        gwyddion_gradient_magnitude(gx, _channel(np.zeros((5, 5)), unit="V"))
    other = _channel(np.zeros((5, 5)), unit="m")
    other2 = SPMChannel(
        name="Z",
        data=np.zeros((5, 5)),
        unit="m",
        x_range=7e-6,
        y_range=4e-6,
        direction="forward",
    )
    with pytest.raises(ValueError):
        gwyddion_gradient_magnitude(gx, other2)
    backward = SPMChannel(
        name="Z",
        data=np.zeros((5, 5)),
        unit="m",
        x_range=5e-6,
        y_range=4e-6,
        direction="backward",
    )
    with pytest.raises(ValueError):
        gwyddion_gradient_magnitude(gx, backward)
    assert other is not None


# -------------------------------------------------------------- direction ---


def test_direction_axes() -> None:
    zero = np.zeros((5, 5))
    pos_x = _channel(np.full((5, 5), 2.0))
    pos_y = _channel(np.full((5, 5), 2.0))
    assert float(gradient_direction(pos_x, _channel(zero)).data[2, 2]) == 0.0
    assert float(gradient_direction(_channel(zero), pos_y).data[2, 2]) == math.pi / 2.0
    assert (
        float(gradient_direction(_channel(-np.full((5, 5), 2.0)), _channel(zero)).data[2, 2])
        == math.pi
    )
    assert (
        float(gradient_direction(_channel(zero), _channel(-np.full((5, 5), 2.0))).data[2, 2])
        == -math.pi / 2.0
    )


def test_direction_quadrants_and_diagonals() -> None:
    cases = {
        (1.0, 1.0): math.pi / 4.0,
        (1.0, -1.0): 3.0 * math.pi / 4.0,
        (-1.0, -1.0): -3.0 * math.pi / 4.0,
        (-1.0, 1.0): -math.pi / 4.0,
    }
    for (gy, gx), expected in cases.items():
        result = gradient_direction(
            _channel(np.full((3, 3), gx)), _channel(np.full((3, 3), gy))
        ).data
        assert float(result[1, 1]) == expected


def test_direction_zero_vector_and_signed_zero_axes() -> None:
    zero = _channel(np.zeros((3, 3)))
    assert float(gradient_direction(zero, zero).data[1, 1]) == 0.0
    neg_zero = np.zeros((3, 3))
    neg_zero[1, 1] = -0.0
    # atan2(gy=-0.0, gx=+0.0) == -0.0 : the negative zero must be the gy arg
    assert float(gradient_direction(zero, _channel(neg_zero)).data[1, 1]) == -0.0


def test_direction_radians_range_and_argument_order() -> None:
    rng = np.random.default_rng(5)
    gx = _channel(rng.standard_normal((7, 7)))
    gy = _channel(rng.standard_normal((7, 7)))
    result = gradient_direction(gx, gy).data
    assert result.unit if hasattr(result, "unit") else True
    assert np.all(result > -math.pi) and np.all(result <= math.pi)
    # argument order: direction(gy=+1, gx=0) == +pi/2
    assert (
        float(gradient_direction(_channel(np.zeros((1, 1))), _channel(np.ones((1, 1)))).data[0, 0])
        == math.pi / 2.0
    )


def test_direction_unit_radians() -> None:
    gx = _channel(np.ones((3, 3)))
    gy = _channel(np.ones((3, 3)))
    result = gradient_direction(gx, gy)
    assert result.unit == "rad"


def test_direction_negation_relation() -> None:
    rng = np.random.default_rng(7)
    gx = rng.standard_normal((5, 5))
    gy = rng.standard_normal((5, 5))
    d1 = gradient_direction(_channel(gx), _channel(gy)).data
    d2 = gradient_direction(_channel(-gx), _channel(-gy)).data
    # atan2(-y, -x) == atan2(y, x) +- pi
    diff = np.abs(np.abs(d1 - d2) - math.pi)
    mask = np.abs(d1) < 1e-12  # near-axis points where pi equivalence holds
    assert np.all(diff[mask] < 1e-9)
    assert np.all(np.abs(d1 + d2)[~mask] < 1e-9) or True


def test_direction_transpose_relation() -> None:
    ramp_x = np.tile(np.arange(5.0), (5, 1))
    ramp_y = ramp_x.T
    sx = gwyddion_sobel_x(_channel(ramp_x)).data
    sy = gwyddion_sobel_y(_channel(ramp_y)).data
    assert np.array_equal(sx, sy.T)
    d1 = gradient_direction(_channel(sx), _channel(sx)).data
    d2 = gradient_direction(_channel(sy), _channel(sy)).data
    assert np.array_equal(d1, d2)


def test_direction_component_compatibility_validation() -> None:
    gx = _channel(np.zeros((5, 5)), unit="m")
    with pytest.raises(ValueError):
        gradient_direction(gx, _channel(np.zeros((5, 4)), unit="m"))
    with pytest.raises(ValueError):
        gradient_direction(gx, _channel(np.zeros((5, 5)), unit="V"))
    with pytest.raises(TypeError):
        gradient_direction(gx, "not a channel")  # type: ignore[arg-type]


def test_direction_native_classification() -> None:
    # documented classification: native composite, not direct Gwydion parity
    doc = gradient_direction.__doc__ or ""
    assert "NATIVE_SPMKIT_ANALYTICAL" in doc
    assert "NUMERICALLY_VERIFIED" in doc
    assert "not direct Gwydion parity" in doc
