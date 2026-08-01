"""Tests for the Gwyddion-compatible Revolve Arc numerical kernel."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis._gwyddion_arc_revolution import (
    _gwyddion_round_positive,
    _make_gwyddion_arc,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, 0),
        (1.49, 1),
        (1.5, 2),
        (2.49, 2),
        (2.5, 3),
        (3.5, 4),
        (4.5, 5),
        (7.999999999999, 8),
        (8.0, 8),
    ],
)
def test_gwyddion_round_uses_half_up_semantics(
    value: float,
    expected: int,
) -> None:
    assert _gwyddion_round_positive(value) == expected


@pytest.mark.parametrize(
    "value",
    [True, "2.5", [2.5], 1.0 + 1.0j],
)
def test_gwyddion_round_rejects_non_real_scalars(value: object) -> None:
    with pytest.raises(TypeError):
        _gwyddion_round_positive(value)


@pytest.mark.parametrize(
    "value",
    [-1.0, np.nan, np.inf, -np.inf],
)
def test_gwyddion_round_rejects_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        _gwyddion_round_positive(value)


@pytest.mark.parametrize(
    ("radius", "maxres", "expected"),
    [
        (
            1.0,
            7,
            np.array(
                [
                    1.0,
                    0.0,
                    1.0,
                ]
            ),
        ),
        (
            2.49,
            7,
            np.array(
                [
                    0.40430786866297319,
                    0.084187639942432058,
                    0.0,
                    0.084187639942432058,
                    0.40430786866297319,
                ]
            ),
        ),
        (
            2.5,
            7,
            np.array(
                [
                    1.0,
                    0.40000000000000013,
                    0.083484861008832012,
                    0.0,
                    0.083484861008832012,
                    0.40000000000000013,
                    1.0,
                ]
            ),
        ),
        (
            4.0,
            16,
            np.array(
                [
                    1.0,
                    0.33856217223385232,
                    0.1339745962155614,
                    0.031754163448145745,
                    0.0,
                    0.031754163448145745,
                    0.1339745962155614,
                    0.33856217223385232,
                    1.0,
                ]
            ),
        ),
        (
            20.0,
            3,
            np.array(
                [
                    0.011314003335740508,
                    0.0050125628933800348,
                    0.0012507822280910519,
                    0.0,
                    0.0012507822280910519,
                    0.0050125628933800348,
                    0.011314003335740508,
                ]
            ),
        ),
        (
            1000.0,
            7,
            np.array(
                [
                    2.4500300132353065e-05,
                    1.8000162002915999e-05,
                    1.2500078125976563e-05,
                    8.000032000256001e-06,
                    4.5000101250455631e-06,
                    2.0000020000040001e-06,
                    5.0000012500006248e-07,
                    0.0,
                    5.0000012500006248e-07,
                    2.0000020000040001e-06,
                    4.5000101250455631e-06,
                    8.000032000256001e-06,
                    1.2500078125976563e-05,
                    1.8000162002915999e-05,
                    2.4500300132353065e-05,
                ]
            ),
        ),
    ],
)
def test_make_arc_matches_gwyddion_2_71_reference(
    radius: float,
    maxres: int,
    expected: np.ndarray,
) -> None:
    result = _make_gwyddion_arc(radius, maxres)

    np.testing.assert_allclose(
        result,
        expected,
        atol=5e-16,
        rtol=0.0,
    )


def test_half_integer_radius_changes_arc_resolution() -> None:
    below_half = _make_gwyddion_arc(2.49, 7)
    half_up = _make_gwyddion_arc(2.5, 7)

    assert below_half.shape == (5,)
    assert half_up.shape == (7,)


def test_arc_is_symmetric_centered_float64_and_read_only() -> None:
    arc = _make_gwyddion_arc(4.0, 16)

    assert arc.dtype == np.float64
    assert arc.shape == (9,)
    assert arc[arc.size // 2] == 0.0
    np.testing.assert_array_equal(arc, arc[::-1])
    assert not arc.flags.writeable


@pytest.mark.parametrize(
    "radius",
    [0.0, -1.0, np.nan, np.inf, -np.inf],
)
def test_make_arc_rejects_invalid_radius(radius: float) -> None:
    with pytest.raises(ValueError):
        _make_gwyddion_arc(radius, 7)


@pytest.mark.parametrize(
    "radius",
    [True, "2.5", [2.5], 1.0 + 1.0j],
)
def test_make_arc_rejects_non_real_radius(radius: object) -> None:
    with pytest.raises(TypeError):
        _make_gwyddion_arc(radius, 7)


@pytest.mark.parametrize(
    "maxres",
    [0, -1],
)
def test_make_arc_rejects_non_positive_resolution(maxres: int) -> None:
    with pytest.raises(ValueError):
        _make_gwyddion_arc(2.5, maxres)


@pytest.mark.parametrize(
    "maxres",
    [True, 3.5, "7", [7]],
)
def test_make_arc_rejects_non_integer_resolution(maxres: object) -> None:
    with pytest.raises(TypeError):
        _make_gwyddion_arc(2.5, maxres)
