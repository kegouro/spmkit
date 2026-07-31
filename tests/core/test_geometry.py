"""Tests for physical geometry primitives."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.geometry import (
    bilinear_sample,
    length_scale_to_metres,
    length_values_from_metres,
    length_values_to_metres,
    physical_to_pixel_indices,
    pixel_center_axes,
)


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("m", 1.0),
        ("mm", 1e-3),
        ("µm", 1e-6),
        ("μm", 1e-6),
        ("um", 1e-6),
        ("nm", 1e-9),
        ("pm", 1e-12),
        ("Å", 1e-10),
        ("angstrom", 1e-10),
    ],
)
def test_length_scale_to_metres_supports_geometric_units(
    unit: str,
    expected: float,
) -> None:
    assert length_scale_to_metres(unit) == expected


@pytest.mark.parametrize("unit", ["V", "A", "nN", "arbitrary"])
def test_length_scale_to_metres_rejects_non_length_units(
    unit: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="unsupported geometric length unit",
    ):
        length_scale_to_metres(unit)


def test_length_value_conversion_round_trip() -> None:
    values = np.array([-3.0, 0.0, 12.5])

    metres = length_values_to_metres(values, unit="nm")
    recovered = length_values_from_metres(metres, unit="nm")

    assert np.allclose(
        metres,
        values * 1e-9,
    )
    assert np.allclose(recovered, values)


def test_pixel_center_axes_use_physical_pixel_centres() -> None:
    x_coordinates, y_coordinates = pixel_center_axes(
        (2, 4),
        x_range=4.0,
        y_range=2.0,
    )

    assert np.allclose(
        x_coordinates,
        [-1.5, -0.5, 0.5, 1.5],
    )
    assert np.allclose(
        y_coordinates,
        [-0.5, 0.5],
    )


def test_physical_coordinates_round_trip_to_pixel_indices() -> None:
    shape = (3, 5)
    x_coordinates, y_coordinates = pixel_center_axes(
        shape,
        x_range=10.0,
        y_range=6.0,
    )
    xx, yy = np.meshgrid(
        x_coordinates,
        y_coordinates,
    )

    x_indices, y_indices = physical_to_pixel_indices(
        xx,
        yy,
        shape=shape,
        x_range=10.0,
        y_range=6.0,
    )

    expected_x, expected_y = np.meshgrid(
        np.arange(shape[1], dtype=float),
        np.arange(shape[0], dtype=float),
    )

    assert np.allclose(x_indices, expected_x)
    assert np.allclose(y_indices, expected_y)


def test_bilinear_sample_is_exact_for_affine_surface() -> None:
    yy, xx = np.mgrid[0:4, 0:5]
    data = 2.0 * xx - 3.0 * yy + 7.0

    sample_x = np.array([0.25, 1.5, 3.75])
    sample_y = np.array([0.5, 2.25, 1.75])

    result = bilinear_sample(
        data,
        x_index=sample_x,
        y_index=sample_y,
    )
    expected = 2.0 * sample_x - 3.0 * sample_y + 7.0

    assert np.allclose(result, expected)


def test_bilinear_sample_nearest_fill_clamps_to_border() -> None:
    data = np.arange(9.0).reshape(3, 3)

    result = bilinear_sample(
        data,
        x_index=np.array([-2.0, 4.0]),
        y_index=np.array([1.0, 1.0]),
        fill_mode="nearest",
    )

    assert np.allclose(result, [3.0, 5.0])


def test_bilinear_sample_constant_fill_marks_outside_domain() -> None:
    data = np.arange(9.0).reshape(3, 3)

    result = bilinear_sample(
        data,
        x_index=np.array([-1.0, 1.0, 3.0]),
        y_index=np.array([1.0, 1.0, 1.0]),
        fill_mode="constant",
        fill_value=-5.0,
    )

    assert np.allclose(result, [-5.0, 4.0, -5.0])


@pytest.mark.parametrize(
    ("shape", "x_range", "y_range", "error_type", "message"),
    [
        (
            (0, 4),
            1.0,
            1.0,
            ValueError,
            "non-empty two-dimensional shape",
        ),
        (
            (3, 4),
            0.0,
            1.0,
            ValueError,
            "x_range to be positive",
        ),
        (
            (3, 4),
            1.0,
            np.inf,
            ValueError,
            "y_range to be finite",
        ),
    ],
)
def test_pixel_center_axes_reject_invalid_geometry(
    shape: tuple[int, int],
    x_range: float,
    y_range: float,
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        pixel_center_axes(
            shape,
            x_range=x_range,
            y_range=y_range,
        )
