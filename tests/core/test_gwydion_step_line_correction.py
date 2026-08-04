"""Core contract tests for Gwydion 2.71 Step Line Correction.

Tests the public and private contracts independently of the frozen fixture
comparison, using source-derived analytic expectations.
"""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import gwydion_step_line_correction
from spmkit.core.analysis._gwydion_step_line_correction import (
    _gwydion_step_line_correction_result,
)
from spmkit.core.models.spmdata import SPMChannel


def _channel(data: np.ndarray) -> SPMChannel:
    return SPMChannel(
        name="test",
        data=np.asarray(data, dtype=np.float64),
        unit="nm",
        x_range=float(data.shape[1]),
        y_range=float(data.shape[0]),
    )


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _make_field(yres: int, xres: int, rows: list[list[float]] | None = None,
                fill: float = 0.0) -> np.ndarray:
    field = np.full((yres, xres), fill, dtype=np.float64)
    if rows:
        for i, row in enumerate(rows):
            field[i, :] = row
    return field


def test_input_non_mutation_and_context_preservation() -> None:
    data = _make_field(5, 7, rows=[
        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]] * 5)
    channel = _channel(data)
    original = data.copy()
    result = gwydion_step_line_correction(channel)
    assert np.array_equal(_bits(channel.data), _bits(original))
    assert result.data.shape == data.shape
    assert result.name == "test"
    assert result.unit == "nm"
    assert result.x_range == 7.0
    assert result.y_range == 5.0
    assert result.metadata == channel.metadata
    assert result is not channel
    assert result.data is not channel.data


def test_output_non_aliasing() -> None:
    data = _make_field(5, 7, fill=2.0)
    result = gwydion_step_line_correction(_channel(data))
    result.data[0, 0] = 12345.0
    assert channel_data_unchanged(data, 12345.0)


def channel_data_unchanged(data: np.ndarray, marker: float) -> bool:
    return not np.any(data == marker)


def test_constant_field_identity() -> None:
    data = _make_field(5, 7, fill=7.25)
    result = gwydion_step_line_correction(_channel(data))
    assert np.array_equal(_bits(result.data), _bits(data))


def test_asymmetric_row_medians() -> None:
    # 4x6 rows: offsets + asymmetric within-row pattern; upper median of
    # [0,2,-1,3,-4,1] is index 3 of the sorted row = 1.0
    rows = []
    for offset in (1.0, 3.0, 2.0, 5.0):
        rows.append([offset + v for v in (0.0, 2.0, -1.0, 3.0, -4.0, 1.0)])
    data = np.array(rows, dtype=np.float64)
    trace = _gwydion_step_line_correction_result(data, trace=True)
    assert list(trace.row_statistics) == [2.0, 4.0, 3.0, 6.0]
    assert list(trace.zero_leveled_shifts) == [-1.75, 0.25, -0.75, 2.25]


def test_accepted_width4_positive_segment() -> None:
    data = _make_field(3, 16, fill=1.0)
    data[1, 2:6] = 2.25  # middle row positive segment, width 4
    trace = _gwydion_step_line_correction_result(data, trace=True)
    # scratch pass 1 carries -1.25 corrections at cols 2..5
    expected = np.zeros((3, 16))
    expected[1, 2:6] = -1.25
    assert np.array_equal(_bits(trace.scratch_pass1), _bits(expected))
    # corrected middle row back to exactly 1.0
    assert np.array_equal(_bits(trace.field_after_pass1[1]), _bits(np.full(16, 1.0)))


def test_rejected_width3_segment() -> None:
    data = _make_field(3, 16, fill=1.0)
    data[1, 2:5] = 2.25  # width 3 < min_len 4
    trace = _gwydion_step_line_correction_result(data, trace=True)
    assert not np.any(trace.scratch_pass1 != 0.0)


def test_negative_segment() -> None:
    data = _make_field(3, 16, fill=1.0)
    data[1, 2:6] = -0.25  # middle row negative segment, width 4
    trace = _gwydion_step_line_correction_result(data, trace=True)
    expected = np.zeros((3, 16))
    expected[1, 2:6] = 1.25
    assert np.array_equal(_bits(trace.scratch_pass1), _bits(expected))


def test_left_and_right_boundary_segments() -> None:
    data = _make_field(3, 16, fill=1.0)
    data[1, 0:4] = 2.25
    trace = _gwydion_step_line_correction_result(data, trace=True)
    expected = np.zeros((3, 16))
    expected[1, 0:4] = -1.25
    assert np.array_equal(_bits(trace.scratch_pass1), _bits(expected))

    data = _make_field(3, 16, fill=1.0)
    data[1, 12:16] = 2.25
    trace = _gwydion_step_line_correction_result(data, trace=True)
    expected = np.zeros((3, 16))
    expected[1, 12:16] = -1.25
    assert np.array_equal(_bits(trace.scratch_pass1), _bits(expected))


def test_two_separated_segments() -> None:
    data = _make_field(3, 28, fill=1.0)
    data[1, 4:8] = 2.25
    data[1, 14:18] = 2.25
    trace = _gwydion_step_line_correction_result(data, trace=True)
    expected = np.zeros((3, 28))
    expected[1, 4:8] = -1.25
    expected[1, 14:18] = -1.25
    assert np.array_equal(_bits(trace.scratch_pass1), _bits(expected))


def test_persistent_transition_no_detector_action() -> None:
    # persistent monotonic transition: v = (middle-top)*(middle-bottom) = 0
    data = _make_field(3, 6)
    data[0, :] = [1.0, 1.0, 1.0, 3.0, 3.0, 3.0]
    data[1, :] = [2.0, 2.0, 2.0, 4.0, 4.0, 4.0]
    data[2, :] = [2.0, 2.0, 2.0, 4.0, 4.0, 4.0]
    trace = _gwydion_step_line_correction_result(data, trace=True)
    assert not np.any(trace.scratch_pass1 != 0.0)
    assert not np.any(trace.scratch_pass2 != 0.0)


def test_conservative_filter_modifies_without_accepted_segment() -> None:
    # single-pixel outlier on the middle row of a 5-row field: marked but
    # below min_len 4, so only the filter changes it (5x5 runs).
    data = _make_field(5, 8, fill=1.0)
    data[2, 3] = 5.0
    trace = _gwydion_step_line_correction_result(data, trace=True)
    assert trace.field_after_pass2[2, 3] == 5.0
    assert trace.field_after_conservative_filter[2, 3] == 1.0
    # mean restoration: final field is 1.1 everywhere (44/40 - 1.0 + 1.0)
    assert trace.final_corrected[0, 0] == 1.1
    assert trace.final_corrected[2, 3] == 1.1


def test_pass2_only_change() -> None:
    # s11 frozen construction: middle row cols 1..4 = 1.75, cols 5..10 = 0.5
    data = _make_field(3, 21, fill=1.0)
    data[1, 1:5] = 1.75
    data[1, 5:11] = 0.5
    trace = _gwydion_step_line_correction_result(data, trace=True)
    changed = np.flatnonzero(
        _bits(trace.field_after_pass1).ravel() != _bits(trace.field_after_pass2).ravel())
    assert list(changed) == [21 + c for c in range(5, 11)]
    assert np.all(trace.field_after_pass2[1, 5:11] == 1.0)


@pytest.mark.parametrize("shape,fill", [((1, 1), 3.5), ((1, 5), 2.0),
                                        ((2, 5), 1.0), ((3, 2), 0.0)])
def test_degenerate_dimensions(shape, fill) -> None:
    data = _make_field(shape[0], shape[1], fill=fill)
    if shape == (1, 1):
        data[0, 0] = 3.5
    elif shape == (1, 5):
        data[0, :] = [0.5, 1.0, 1.5, 2.0, 2.5]
    elif shape == (2, 5):
        data[0, :] = [0.0, 1.0, 2.0, 3.0, 4.0]
        data[1, :] = [5.0, 6.0, 7.0, 8.0, 9.0]
    else:
        data[0, :] = [0.0, 1.0]
        data[1, :] = [2.0, 3.0]
        data[2, :] = [4.0, 5.0]
    # must run without error and preserve shape/dtype
    result = gwydion_step_line_correction(_channel(data))
    assert result.data.shape == shape
    assert result.data.dtype == np.float64
    assert np.isfinite(result.data).all()


def test_signed_zero_behaviour() -> None:
    data = _make_field(3, 8, fill=0.0)
    data[1, 0:4] = -0.0
    result = gwydion_step_line_correction(_channel(data))
    neg = int(np.count_nonzero(_bits(result.data) == 0x8000000000000000))
    assert neg == 0  # pipeline converts -0.0 to +0.0


def test_finite_float64_output() -> None:
    data = _make_field(5, 7, fill=1.0)
    data[2, 3] = 5.0
    result = gwydion_step_line_correction(_channel(data))
    assert result.data.dtype == np.float64
    assert np.isfinite(result.data).all()


@pytest.mark.parametrize("bad", [
    np.array([[1.0, np.nan], [2.0, 3.0]]),
    np.array([[1.0, np.inf], [2.0, 3.0]]),
    np.array([[1.0, -np.inf], [2.0, 3.0]]),
])
def test_non_finite_rejection(bad) -> None:
    with pytest.raises(ValueError, match="finite"):
        gwydion_step_line_correction(_channel(bad))


def test_non_2d_and_empty_rejection() -> None:
    with pytest.raises(ValueError, match="two-dimensional"):
        gwydion_step_line_correction(SPMChannel(
            name="t", data=np.array([1.0, 2.0, 3.0]), unit="nm",
            x_range=3.0, y_range=1.0))
    with pytest.raises(ValueError, match="non-empty"):
        gwydion_step_line_correction(_channel(np.zeros((0, 5))))
