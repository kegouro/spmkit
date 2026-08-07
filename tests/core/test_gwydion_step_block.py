"""Core contract tests for gwydion_step_block_correction (production).

Analytical and metamorphic expectations only; the frozen compiled fixtures
are NOT read from core tests.
"""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import gwydion_step_block_correction
from spmkit.core.models.spmdata import SPMChannel


def _channel(data: np.ndarray, name: str = "stepblock") -> SPMChannel:
    return SPMChannel(
        name=name, data=np.asarray(data, dtype=np.float64), unit="nm",
        x_range=float(data.shape[1]), y_range=float(data.shape[0]),
        metadata={"Dim1Name": "Y", "custom": 11})


def _field(rows: int, cols: int, band_row: int | None = None,
           band_value: float = 5.0) -> np.ndarray:
    field = np.zeros((rows, cols), dtype=np.float64)
    if band_row is not None:
        field[band_row:, :] = band_value
    return field


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def test_constant_noop() -> None:
    field = np.full((16, 16), 3.0)
    out = gwydion_step_block_correction(_channel(field))
    assert np.array_equal(_bits(out.data), _bits(field))


def test_single_positive_step() -> None:
    field = _field(16, 16, 8, 5.0)
    out = gwydion_step_block_correction(_channel(field))
    # the step is detected and corrected: the field becomes piecewise flat
    assert np.array_equal(_bits(out.data), _bits(np.zeros((16, 16))))


def test_single_negative_step() -> None:
    field = _field(16, 16, 8, -5.0)
    out = gwydion_step_block_correction(_channel(field))
    assert np.array_equal(_bits(out.data), _bits(np.zeros((16, 16))))


def test_multiple_cumulative_blocks() -> None:
    field = _field(24, 16, 8, 5.0)
    field[16:, :] = 10.0
    out = gwydion_step_block_correction(_channel(field))
    assert np.array_equal(_bits(out.data), _bits(np.zeros((24, 16))))


def test_alternating_offsets() -> None:
    field = np.zeros((32, 16), dtype=np.float64)
    field[8:16, :] = 3.0
    field[16:24, :] = 1.0
    field[24:, :] = 4.0
    out = gwydion_step_block_correction(_channel(field))
    assert np.all(out.data == 0.0)


def test_left_to_right() -> None:
    field = _field(16, 16, 8, 5.0)
    out = gwydion_step_block_correction(_channel(field),
                                        direction="left_to_right")
    assert np.array_equal(_bits(out.data), _bits(np.zeros((16, 16))))


def test_right_to_left() -> None:
    field = _field(16, 16, 8, 5.0)
    out = gwydion_step_block_correction(_channel(field),
                                        direction="right_to_left")
    assert np.array_equal(_bits(out.data), _bits(np.zeros((16, 16))))


def test_partial_width_boundary() -> None:
    field = np.zeros((16, 16), dtype=np.float64)
    field[8:, 0:12] = 5.0
    out = gwydion_step_block_correction(_channel(field))
    # the 12/16 partial step is detected with a horizontal split at
    # column 12; the stepped region is corrected to 0, while the boundary
    # row's right segment (already 0) is pulled down by the cumulative
    # shift, reproducing the source's boundary-row segmentation
    assert np.all(out.data[8:, 0:12] == 0.0)
    assert np.all(out.data[7:, 12:16] == -5.0)
    assert np.all(out.data[0:7, :] == 0.0)


def test_threshold_below_detection() -> None:
    field = _field(16, 16, 8, 5.0)
    out = gwydion_step_block_correction(_channel(field), threshold=4.5)
    assert np.array_equal(_bits(out.data), _bits(field))


def test_exact_threshold_strict_comparison() -> None:
    # yres=17 with threshold=4.0 makes the effective threshold exactly equal
    # to the step height: the strict > comparison yields no detection
    field = _field(17, 16, 8, 5.0)
    out = gwydion_step_block_correction(_channel(field), threshold=4.0)
    assert np.array_equal(_bits(out.data), _bits(field))


def test_non_square_field() -> None:
    field = _field(8, 64, 4, 5.0)
    out = gwydion_step_block_correction(_channel(field))
    assert np.all(out.data == 0.0)


def test_yres_one_valid_noop() -> None:
    field = np.zeros((1, 16), dtype=np.float64)
    out = gwydion_step_block_correction(_channel(field))
    assert np.array_equal(_bits(out.data), _bits(field))


def test_xres_two_valid_behavior() -> None:
    field = _field(8, 2, 4, 5.0)
    out = gwydion_step_block_correction(_channel(field))
    assert np.all(out.data == 0.0)


def test_xres_one_rejected() -> None:
    field = np.zeros((8, 1), dtype=np.float64)
    with pytest.raises(ValueError) as exc:
        gwydion_step_block_correction(_channel(field))
    assert "xres < 2" in str(exc.value)


def test_zero_column_rejected() -> None:
    field = np.zeros((8, 0), dtype=np.float64)
    with pytest.raises(ValueError):
        gwydion_step_block_correction(_channel(field))


def test_non_finite_rejected() -> None:
    field = np.zeros((8, 8), dtype=np.float64)
    field[2, 2] = np.nan
    with pytest.raises(ValueError):
        gwydion_step_block_correction(_channel(field))
    field[2, 2] = np.inf
    with pytest.raises(ValueError):
        gwydion_step_block_correction(_channel(field))


def test_threshold_below_minimum() -> None:
    with pytest.raises(ValueError):
        gwydion_step_block_correction(_channel(np.zeros((8, 8))),
                                      threshold=0.05)


def test_threshold_above_maximum() -> None:
    with pytest.raises(ValueError):
        gwydion_step_block_correction(_channel(np.zeros((8, 8))),
                                      threshold=10.5)


def test_invalid_direction() -> None:
    with pytest.raises(ValueError):
        gwydion_step_block_correction(_channel(np.zeros((8, 8))),
                                      direction="top_to_bottom")


def test_input_channel_non_mutation() -> None:
    field = _field(16, 16, 8, 5.0)
    ch = _channel(field)
    before = _bits(field).copy()
    gwydion_step_block_correction(ch)
    assert np.array_equal(_bits(field), before)


def test_input_ndarray_non_mutation() -> None:
    field = _field(16, 16, 8, 5.0)
    before = _bits(field).copy()
    gwydion_step_block_correction(_channel(field))
    assert np.array_equal(_bits(field), before)


def test_context_preservation() -> None:
    field = _field(16, 16, 8, 5.0)
    ch = _channel(field)
    out = gwydion_step_block_correction(ch)
    assert out.name == ch.name
    assert out.unit == ch.unit
    assert out.x_range == ch.x_range
    assert out.y_range == ch.y_range
    assert out.direction == ch.direction
    assert out.group == ch.group
    assert out.metadata == ch.metadata
    assert out is not ch


def test_signed_zero_noop() -> None:
    field = np.full((16, 16), -0.0)
    out = gwydion_step_block_correction(_channel(field))
    assert np.array_equal(_bits(out.data), _bits(field))


def test_output_independent_of_later_input_mutation() -> None:
    field = _field(16, 16, 8, 5.0)
    out = gwydion_step_block_correction(_channel(field))
    field[0, 0] = 99.0
    out2 = gwydion_step_block_correction(_channel(field))
    assert out.data[0, 0] == 0.0
    assert out2.data[0, 0] == 99.0


def test_no_mask_parameter() -> None:
    # the public API must not accept a mask
    field = _field(16, 16, 8, 5.0)
    with pytest.raises(TypeError):
        gwydion_step_block_correction(_channel(field), mask=np.zeros((16, 16)))
