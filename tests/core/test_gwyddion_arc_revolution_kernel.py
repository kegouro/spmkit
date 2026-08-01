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


def _asymmetric_reference_field() -> np.ndarray:
    data = np.empty((5, 7), dtype=float)

    for row in range(5):
        for column in range(7):
            value = (
                2.0
                + 0.12 * column
                - 0.07 * row
                + 0.015 * column * row
                + 0.03 * np.sin(0.9 * column + 0.4 * row)
            )

            if row == 1 and column == 4:
                value += 3.5
            if row == 3 and column == 2:
                value -= 4.0
            if row == 4 and column == 6:
                value += 1.2

            data[row, column] = value

    return data


def _independent_truncated_moving_sums(
    row: np.ndarray,
    size: int,
) -> tuple[np.ndarray, np.ndarray]:
    left_half = size // 2
    right_half = 0 if size == 0 else (size - 1) // 2

    sums = np.empty(row.size, dtype=float)
    squared_sums = np.empty(row.size, dtype=float)

    for index in range(row.size):
        start = max(0, index - left_half)
        stop = min(row.size, index + right_half + 1)
        window = row[start:stop]

        sums[index] = sum(float(value) for value in window)
        squared_sums[index] = sum(float(value) ** 2 for value in window)

    return sums, squared_sums


def test_population_rms_matches_gwyddion_reference() -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_population_rms,
    )

    data = _asymmetric_reference_field()
    rms = _gwyddion_population_rms(data)
    scale = rms / np.sqrt(2.0 / 3.0 - np.pi / 16.0)

    assert scale == pytest.approx(
        1.485841488666283,
        abs=2e-15,
        rel=0.0,
    )


@pytest.mark.parametrize("size", range(0, 6))
def test_moving_sums_match_independent_truncated_oracle(size: int) -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import _moving_sums

    row = np.array([1.0, -2.0, 4.0, 8.0, -1.0, 3.0])
    expected_sum, expected_sum2 = _independent_truncated_moving_sums(
        row,
        size,
    )

    result_sum, result_sum2 = _moving_sums(
        row,
        size,
    )

    np.testing.assert_array_equal(result_sum, expected_sum)
    np.testing.assert_array_equal(result_sum2, expected_sum2)


@pytest.mark.parametrize(
    ("size", "expected_sum", "expected_sum2"),
    [
        (
            6,
            np.array([3.0, 11.0, 10.0, 10.0, 9.0, 11.0]),
            np.array([21.0, 85.0, 86.0, 86.0, 85.0, 81.0]),
        ),
        (
            7,
            np.array([11.0, 10.0, 10.0, 10.0, 9.0, 11.0]),
            np.array([85.0, 86.0, 86.0, 86.0, 85.0, 81.0]),
        ),
    ],
)
def test_moving_sums_match_gwyddion_whale_branch(
    size: int,
    expected_sum: np.ndarray,
    expected_sum2: np.ndarray,
) -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import _moving_sums

    row = np.array([1.0, -2.0, 4.0, 8.0, -1.0, 3.0])

    result_sum, result_sum2 = _moving_sums(
        row,
        size,
    )

    np.testing.assert_array_equal(result_sum, expected_sum)
    np.testing.assert_array_equal(result_sum2, expected_sum2)


def test_moving_sums_reproduce_reference_large_window_shortcut() -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import _moving_sums

    row = np.array([1.0, -2.0, 4.0, 8.0, -1.0, 3.0])
    result_sum, result_sum2 = _moving_sums(row, 13)

    np.testing.assert_array_equal(
        result_sum,
        np.ones(6),
    )
    np.testing.assert_array_equal(
        result_sum2,
        np.ones(6),
    )


def test_moving_sums_reject_reference_undefined_memory_case() -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import _moving_sums

    with pytest.raises(
        ValueError,
        match="undefined",
    ):
        _moving_sums(
            np.array([4.0]),
            1,
        )


def test_horizontal_kernel_matches_asymmetric_gwyddion_reference() -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_horizontal,
    )

    expected = np.array(
        [
            [2.0, 2.1240452701624606, 2.2675450774512851,
             2.3728213964070148, 2.4667243867011543,
             2.570674096470047, 2.6947193666325076],
            [1.9416825502692594, 2.0657278204317202,
             2.2179520157249768, 2.3362474198729988,
             2.4602926900354594, 2.5755264216212703,
             2.6995716917837309],
            [1.8815206827269855, 2.0055659528894463,
             2.1637952144760346, 2.299476503169311,
             2.4235217733317715, 2.5554972079457752,
             2.7090772468957436],
            [-1.2814298042916905, -1.7517211295957433,
             -1.8757663997582039, -1.7517211295957433,
             -1.2814298042916905, -0.38992491109192096,
             2.7225247038845315],
            [1.7499872080912451, 1.8740324782537057,
             2.0419994344855796, 2.1963790371016558,
             2.3565602920599771, 2.5375416304908565,
             2.738580395034298],
        ]
    )

    result = _gwyddion_arc_horizontal(
        _asymmetric_reference_field(),
        2.5,
    )

    np.testing.assert_allclose(
        result,
        expected,
        atol=5e-15,
        rtol=0.0,
    )


def test_horizontal_kernel_preserves_constant_field() -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_horizontal,
    )

    data = np.full((2, 5), 3.25)
    result = _gwyddion_arc_horizontal(data, 2.5)

    np.testing.assert_array_equal(result, data)


def test_horizontal_kernel_matches_single_row_reference() -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_horizontal,
    )

    data = np.array([[0.0, 1.0, -2.0, 4.0, 1.0]])
    expected = np.array(
        [[
            0.0,
            -1.2800008456684795,
            -2.0,
            -1.2800008456684795,
            0.82747338686665239,
        ]]
    )

    result = _gwyddion_arc_horizontal(data, 1.5)

    np.testing.assert_allclose(
        result,
        expected,
        atol=5e-15,
        rtol=0.0,
    )


def test_horizontal_kernel_matches_large_radius_reference() -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_horizontal,
    )

    data = np.array(
        [
            [0.0, 1.0, 4.0, 2.0, -1.0, 3.0, 0.0],
            [2.0, 2.5, 1.0, 0.0, -2.0, 1.0, 4.0],
        ]
    )
    expected = np.array(
        [
            [
                -0.99997994598602924,
                -0.9999887196368823,
                -0.99999498651154795,
                -0.99999874662882704,
                -1.0,
                -0.99999874662882704,
                -0.99999498651154795,
            ],
            [
                -1.9999799459860292,
                -1.9999887196368822,
                -1.9999949865115478,
                -1.9999987466288269,
                -2.0,
                -1.9999987466288269,
                -1.9999949865115478,
            ],
        ]
    )

    result = _gwyddion_arc_horizontal(data, 1000.0)

    np.testing.assert_allclose(
        result,
        expected,
        atol=5e-15,
        rtol=0.0,
    )


def test_horizontal_kernel_defines_one_sample_axis_as_identity() -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_horizontal,
    )

    data = np.array([[0.0], [-1.0], [2.0], [5.0]])
    result = _gwyddion_arc_horizontal(data, 2.5)

    np.testing.assert_array_equal(result, data)


def test_horizontal_kernel_does_not_mutate_input_and_returns_read_only() -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_horizontal,
    )

    data = _asymmetric_reference_field()
    original = data.copy()

    result = _gwyddion_arc_horizontal(data, 2.5)

    np.testing.assert_array_equal(data, original)
    assert result.dtype == np.float64
    assert not result.flags.writeable


@pytest.mark.parametrize(
    ("direction", "inverted"),
    [
        ("horizontal", False),
        ("horizontal", True),
        ("vertical", False),
        ("vertical", True),
        ("both", False),
        ("both", True),
    ],
)
def test_directional_background_matches_explicit_composition(
    direction: str,
    inverted: bool,
) -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_background,
        _gwyddion_arc_horizontal,
    )

    data = _asymmetric_reference_field()
    working = -data if inverted else data

    if direction == "horizontal":
        expected = _gwyddion_arc_horizontal(
            working,
            2.5,
        )
    elif direction == "vertical":
        expected = _gwyddion_arc_horizontal(
            working.T,
            2.5,
        ).T
    else:
        horizontal = _gwyddion_arc_horizontal(
            working,
            2.5,
        )
        expected = _gwyddion_arc_horizontal(
            horizontal.T,
            2.5,
        ).T

    if inverted:
        expected = -expected

    result = _gwyddion_arc_background(
        data,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    )

    np.testing.assert_array_equal(result, expected)


@pytest.mark.parametrize(
    ("direction", "inverted"),
    [
        ("horizontal", False),
        ("horizontal", True),
        ("vertical", False),
        ("vertical", True),
        ("both", False),
        ("both", True),
    ],
)
def test_directional_corrected_reconstructs_input(
    direction: str,
    inverted: bool,
) -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_background,
        _gwyddion_arc_corrected,
    )

    data = _asymmetric_reference_field()
    original = data.copy()

    background = _gwyddion_arc_background(
        data,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    )
    corrected = _gwyddion_arc_corrected(
        data,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    )

    np.testing.assert_array_equal(data, original)
    np.testing.assert_allclose(
        corrected + background,
        data,
        atol=5e-15,
        rtol=0.0,
    )

    assert background.dtype == np.float64
    assert corrected.dtype == np.float64
    assert background.flags.c_contiguous
    assert corrected.flags.c_contiguous
    assert not background.flags.writeable
    assert not corrected.flags.writeable


@pytest.mark.parametrize(
    "direction",
    ["horizontal", "vertical", "both"],
)
@pytest.mark.parametrize(
    "inverted",
    [False, True],
)
def test_directional_one_by_one_field_is_identity(
    direction: str,
    inverted: bool,
) -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_background,
        _gwyddion_arc_corrected,
    )

    data = np.array([[4.25]])

    background = _gwyddion_arc_background(
        data,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    )
    corrected = _gwyddion_arc_corrected(
        data,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    )

    np.testing.assert_array_equal(background, data)
    np.testing.assert_array_equal(
        corrected,
        np.zeros_like(data),
    )


@pytest.mark.parametrize(
    "direction",
    ["diagonal", "", 1],
)
def test_directional_background_rejects_invalid_direction(
    direction: object,
) -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_background,
    )

    expected_exception = (
        TypeError
        if not isinstance(direction, str)
        else ValueError
    )

    with pytest.raises(expected_exception):
        _gwyddion_arc_background(
            np.ones((2, 3)),
            2.5,
            direction=direction,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "inverted",
    [0, 1, "yes", None],
)
def test_directional_background_rejects_non_boolean_inversion(
    inverted: object,
) -> None:
    from spmkit.core.analysis._gwyddion_arc_revolution import (
        _gwyddion_arc_background,
    )

    with pytest.raises(TypeError):
        _gwyddion_arc_background(
            np.ones((2, 3)),
            2.5,
            inverted=inverted,  # type: ignore[arg-type]
        )
