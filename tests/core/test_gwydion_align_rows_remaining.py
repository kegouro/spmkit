"""Core contract tests for the Gwydion 2.71 Align Rows remaining methods
(polynomial, modus, match).

Analytical and metamorphic expectations only; no frozen JSON/NPZ fixtures
are loaded here.
"""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import (
    gwyddion_align_rows_match,
    gwyddion_align_rows_modus,
    gwyddion_align_rows_polynomial,
)
from spmkit.core.models.spmdata import SPMChannel

OPS = (gwyddion_align_rows_polynomial, gwyddion_align_rows_modus,
       gwyddion_align_rows_match)


def _channel(data: np.ndarray, *, name: str = "test") -> SPMChannel:
    cols = data.shape[1] if data.ndim == 2 else 1
    rows = data.shape[0] if data.ndim >= 1 else 1
    return SPMChannel(name=name, data=data, unit="nm", x_range=float(cols),
                      y_range=float(rows), direction="forward",
                      group="g", metadata={"Dim1Name": "Y"})


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


# ---------------------------------------------------------------------------
# COMMON
# ---------------------------------------------------------------------------

def test_invalid_dimension_rejected() -> None:
    for op in OPS:
        with pytest.raises(ValueError, match="two-dimensional"):
            op(_channel(np.zeros(8)))
        with pytest.raises(ValueError, match="non-empty"):
            op(_channel(np.zeros((0, 8))))


def test_non_finite_input_rejected() -> None:
    for op in OPS:
        with pytest.raises(ValueError, match="finite"):
            op(_channel(np.array([[1.0, np.nan], [2.0, 3.0]])))
        with pytest.raises(ValueError, match="finite"):
            op(_channel(np.array([[1.0, np.inf], [2.0, 3.0]])))


def test_mask_shape_mismatch_rejected() -> None:
    data = np.arange(24, dtype=float).reshape(4, 6)
    bad_mask = np.zeros((3, 6))
    for op in OPS:
        with pytest.raises(ValueError, match="mask shape"):
            op(_channel(data), mask=bad_mask, mask_mode="include")


def test_invalid_masking_mode_rejected() -> None:
    data = np.arange(24, dtype=float).reshape(4, 6)
    for op in OPS:
        with pytest.raises(ValueError, match="mask_mode"):
            op(_channel(data), mask_mode="bogus")


def test_include_predicate_gt_zero() -> None:
    # rows with different means; include only the mask > 0 samples
    data = np.array([[0.0, 10.0], [0.0, 10.0], [0.0, 10.0], [0.0, 10.0]])
    mask = np.array([[0.0, 1.0], [0.0, 1.0], [0.0, 1.0], [0.0, 1.0]])
    out = gwyddion_align_rows_polynomial(_channel(data), degree=0, mask=mask,
                                        mask_mode="include")
    # every row's mean is 10 -> shifts zero-level to 0 -> no change
    assert np.array_equal(_bits(out.data), _bits(data))
    # a 0.5-valued mask is NOT included (> 0 strictly)
    mask2 = np.array([[0.0, 0.5], [0.0, 0.5], [0.0, 0.5], [0.0, 0.5]])
    out2 = gwyddion_align_rows_polynomial(_channel(data), degree=0, mask=mask2,
                                         mask_mode="include")
    assert np.array_equal(_bits(out2.data), _bits(data))


def test_exclude_predicate_lt_one() -> None:
    data = np.array([[0.0, 10.0], [0.0, 10.0], [0.0, 10.0], [0.0, 10.0]])
    mask = np.array([[0.0, 1.0], [0.0, 1.0], [0.0, 1.0], [0.0, 1.0]])
    out = gwyddion_align_rows_polynomial(_channel(data), degree=0, mask=mask,
                                        mask_mode="exclude")
    # every row keeps only the 0-mask sample (0) -> shifts zero -> no change
    assert np.array_equal(_bits(out.data), _bits(data))
    # a 0.5-valued mask IS excluded (< 1 strictly)
    mask2 = np.array([[0.0, 0.5], [0.0, 0.5], [0.0, 0.5], [0.0, 0.5]])
    out2 = gwyddion_align_rows_polynomial(_channel(data), degree=0, mask=mask2,
                                         mask_mode="exclude")
    # rows keep 0.0 only -> no change
    assert np.array_equal(_bits(out2.data), _bits(data))


def test_ignore_semantics() -> None:
    data = np.array([[0.0, 10.0], [2.0, 12.0], [4.0, 14.0], [6.0, 16.0]])
    mask = np.zeros_like(data)
    plain = gwyddion_align_rows_polynomial(_channel(data), degree=0)
    ignored = gwyddion_align_rows_polynomial(_channel(data), degree=0,
                                            mask=mask, mask_mode="ignore")
    assert np.array_equal(_bits(plain.data), _bits(ignored.data))


def test_input_channel_and_ndarray_non_mutation() -> None:
    data = np.array([[0.0, 10.0, 20.0], [1.0, 11.0, 21.0], [2.0, 12.0, 22.0]])
    original = data.copy()
    ch = _channel(data)
    before = _bits(data).copy()
    gwyddion_align_rows_polynomial(ch, degree=0)
    gwyddion_align_rows_polynomial(ch, degree=1)
    gwyddion_align_rows_modus(ch)
    gwyddion_align_rows_match(ch)
    assert np.array_equal(_bits(data), before)
    assert np.array_equal(data, original)
    assert ch.name == "test" and ch.unit == "nm"


def test_mask_non_mutation() -> None:
    data = np.arange(36, dtype=float).reshape(6, 6)
    mask = np.zeros_like(data)
    mask[2:4, 2:4] = 1.0
    before = _bits(mask).copy()
    for op in OPS:
        op(_channel(data), mask=mask, mask_mode="include")
        op(_channel(data), mask=mask, mask_mode="exclude")
    assert np.array_equal(_bits(mask), before)


def test_context_preservation() -> None:
    data = np.arange(36, dtype=float).reshape(6, 6)
    ch = _channel(data, name="ctx")
    out = gwyddion_align_rows_polynomial(ch, degree=1)
    assert out.name == "ctx"
    assert out.unit == "nm"
    assert out.x_range == ch.x_range and out.y_range == ch.y_range
    assert out.direction == "forward" and out.group == "g"
    assert out.metadata == {"Dim1Name": "Y"}


def test_vertical_direction_transpose_metamorphic() -> None:
    # vertical processing must equal horizontal processing of the
    # transposed field, transposed back (source execute() flip_xy
    # semantics); shape, calibration and mask orientation stay correct
    rng = np.random.default_rng(3)
    data = rng.normal(size=(7, 9))
    mask = np.zeros_like(data)
    mask[2:5, 3:6] = 1.0
    for op, kw in ((gwyddion_align_rows_polynomial, {"degree": 0}),
                   (gwyddion_align_rows_polynomial, {"degree": 1}),
                   (gwyddion_align_rows_modus, {}),
                   (gwyddion_align_rows_match, {})):
        ver = op(_channel(data), direction="vertical", mask=mask,
                 mask_mode="include", **kw)
        hor_t = op(_channel(data.T), direction="horizontal", mask=mask.T,
                   mask_mode="include", **kw).data
        assert ver.data.shape == data.shape
        assert np.array_equal(_bits(ver.data),
                              _bits(np.ascontiguousarray(hor_t.T)))


def test_output_storage_independence() -> None:
    data = np.arange(36, dtype=float).reshape(6, 6)
    out = gwyddion_align_rows_polynomial(_channel(data), degree=1)
    data[:] = 999.0
    assert not np.any(out.data == 999.0)


def test_signed_zero_behavior() -> None:
    # 12-wide: polynomial degree 0/1 and match preserve -0.0 exactly, and
    # modus takes the count>=9 window branch which also preserves -0.0 in
    # the compiled profile (U12_SIGNED_ZERO)
    data = np.full((4, 12), -0.0)
    for op in OPS:
        out = op(_channel(data))
        assert np.array_equal(_bits(out.data), _bits(data))


# ---------------------------------------------------------------------------
# POLYNOMIAL
# ---------------------------------------------------------------------------

def test_polynomial_degree0_constant_noop() -> None:
    data = np.full((5, 8), 3.0)
    out = gwyddion_align_rows_polynomial(_channel(data), degree=0)
    assert np.array_equal(_bits(out.data), _bits(data))


def test_polynomial_degree0_distinct_row_offsets() -> None:
    data = np.array([[0.0] * 8, [2.0] * 8, [4.0] * 8, [6.0] * 8])
    out = gwyddion_align_rows_polynomial(_channel(data), degree=0)
    # zero-levelled row means: 0,2,4,6 -> -3,-1,1,3 ; corrected = flat at 3
    expected = np.full_like(data, 3.0)
    assert np.array_equal(_bits(out.data), _bits(expected))


def test_polynomial_degree0_insufficient_fallback() -> None:
    # xres=16 -> mincount = floor(log(16)+1.5) = 4; rows with 2 samples
    # fall back to the global median
    data = np.zeros((3, 16))
    data[:, 0] = 100.0
    data[:, 1] = 100.0
    mask = np.zeros_like(data)
    mask[:, 0] = 1.0
    mask[:, 1] = 1.0
    out = gwyddion_align_rows_polynomial(_channel(data), degree=0, mask=mask,
                                        mask_mode="include")
    # all rows fall back to global median 100 -> shifts 0 -> no change
    assert np.array_equal(_bits(out.data), _bits(data))


def test_polynomial_degree1_exact_linear_rows() -> None:
    x = np.arange(8, dtype=float) - 3.5
    data = np.stack([1.0 + 0.25 * i + 0.5 * x for i in range(4)])
    out = gwyddion_align_rows_polynomial(_channel(data), degree=1)
    # removing each row's linear background leaves the constant 1+i, which
    # is row-constant; the polynomial fit removes slope and anchors the mean
    corrected = out.data
    # within-row flatness: each corrected row must be constant
    for row in range(4):
        assert np.allclose(corrected[row], corrected[row, 0], rtol=0, atol=1e-12)


def test_polynomial_mixed_intercept_and_slope() -> None:
    x = np.arange(10, dtype=float) - 4.5
    data = np.stack([-3.0 + i + (2.0 - 0.1 * i) * x for i in range(4)])
    out = gwyddion_align_rows_polynomial(_channel(data), degree=1)
    for row in range(4):
        assert np.allclose(out.data[row], out.data[row, 0], rtol=0, atol=1e-12)


def test_polynomial_degree2_exact_quadratic_rows() -> None:
    x = np.arange(8, dtype=float) - 3.5
    data = np.stack([2.0 + 0.5 * i * x + 0.1 * x * x for i in range(4)])
    out = gwyddion_align_rows_polynomial(_channel(data), degree=2)
    for row in range(4):
        assert np.allclose(out.data[row], out.data[row, 0], rtol=0, atol=1e-9)


def test_polynomial_degree_discrimination() -> None:
    x = np.arange(8, dtype=float) - 3.5
    data = np.stack([i + 0.5 * x + 0.1 * x * x for i in range(4)])
    d0 = gwyddion_align_rows_polynomial(_channel(data), degree=0)
    d1 = gwyddion_align_rows_polynomial(_channel(data), degree=1)
    d2 = gwyddion_align_rows_polynomial(_channel(data), degree=2)
    assert not np.array_equal(_bits(d0.data), _bits(d1.data))
    assert not np.array_equal(_bits(d0.data), _bits(d2.data))
    assert not np.array_equal(_bits(d1.data), _bits(d2.data))


def test_polynomial_masked_fitting() -> None:
    x = np.arange(8, dtype=float) - 3.5
    data = np.stack([1.0 + i + 0.5 * x for i in range(4)])
    # mask the right half: fit uses only j < 4, still removes the slope
    mask = np.zeros_like(data)
    mask[:, :4] = 1.0
    out = gwyddion_align_rows_polynomial(_channel(data), degree=1, mask=mask,
                                        mask_mode="include")
    assert np.allclose(out.data[0], out.data[0, 0], rtol=0, atol=1e-9)


def test_polynomial_insufficient_valid_samples() -> None:
    # 3 valid samples per row, degree 3: guard fails -> coefficients zero,
    # zx[0] -= avg anchors; the correction is the constant -avg
    data = np.arange(80, dtype=float).reshape(10, 8)
    mask = np.zeros_like(data)
    mask[:, :3] = 1.0
    out = gwyddion_align_rows_polynomial(_channel(data), degree=3, mask=mask,
                                        mask_mode="include")
    avg = float(np.mean(data))
    expected = data + avg  # corrected = input - (-avg)
    assert np.array_equal(_bits(out.data), _bits(expected))


def test_polynomial_degree_validation() -> None:
    data = np.arange(24, dtype=float).reshape(4, 6)
    with pytest.raises(ValueError, match="0..5"):
        gwyddion_align_rows_polynomial(_channel(data), degree=6)
    with pytest.raises(ValueError, match="0..5"):
        gwyddion_align_rows_polynomial(_channel(data), degree=-1)
    with pytest.raises(TypeError, match="integer"):
        gwyddion_align_rows_polynomial(_channel(data), degree=1.5)


def test_polynomial_non_square_fields() -> None:
    wide = np.random.default_rng(7).normal(size=(4, 64))
    tall = np.random.default_rng(7).normal(size=(64, 4))
    out_wide = gwyddion_align_rows_polynomial(_channel(wide), degree=1)
    out_tall = gwyddion_align_rows_polynomial(_channel(tall), degree=1)
    assert out_wide.data.shape == wide.shape
    assert out_tall.data.shape == tall.shape


# ---------------------------------------------------------------------------
# MODUS
# ---------------------------------------------------------------------------

def test_modus_constant_rows() -> None:
    data = np.full((5, 10), 7.0)
    out = gwyddion_align_rows_modus(_channel(data))
    assert np.array_equal(_bits(out.data), _bits(data))


def test_modus_distinct_row_centers() -> None:
    data = np.array([[5.0] * 10, [5.0] * 10, [9.0] * 10, [9.0] * 10])
    out = gwyddion_align_rows_modus(_channel(data))
    # row modi 5,5,9,9 -> zero-levelled -2,-2,2,2 -> corrected flat at 7
    expected = np.full_like(data, 7.0)
    assert np.array_equal(_bits(out.data), _bits(expected))


def test_modus_count_lt9_upper_median() -> None:
    # 2 samples per row -> upper median (rank count//2 = 1)
    data = np.array([[0.0, 10.0], [0.0, 10.0], [2.0, 8.0], [2.0, 8.0]])
    out = gwyddion_align_rows_modus(_channel(data))
    # row estimates: 10,10,8,8 -> zero-levelled shifts 1,1,-1,-1
    expected = data - np.array([[1.0], [1.0], [-1.0], [-1.0]])
    assert np.array_equal(_bits(out.data), _bits(expected))


def test_modus_count_ge9_narrowest_window() -> None:
    # 10 samples: 5 zeros + 5 tens -> window 3, narrowest range 0, central
    # third selects a zero -> row estimate 0
    data = np.array([[0.0] * 5 + [10.0] * 5] * 3)
    out = gwyddion_align_rows_modus(_channel(data))
    assert np.array_equal(_bits(out.data), _bits(data))


def test_modus_equal_range_first_tie() -> None:
    # 12 samples: 6 zeros + 6 tens -> multiple range-0 windows; the first
    # strict minimum selects zeros -> estimate 0 (not 10)
    data = np.array([[0.0] * 6 + [10.0] * 6] * 3)
    out = gwyddion_align_rows_modus(_channel(data))
    assert np.array_equal(_bits(out.data), _bits(data))


def test_modus_repeated_values() -> None:
    data = np.array([[2.0, 3.0] + [3.0] * 10, [2.0, 3.0] + [3.0] * 10] * 2)
    out = gwyddion_align_rows_modus(_channel(data))
    # row estimate 3 everywhere -> no correction
    assert np.array_equal(_bits(out.data), _bits(data))


def test_modus_outlier_resistance() -> None:
    data = np.array([[5.0] * 8 + [-100.0, 100.0]] * 3)
    out = gwyddion_align_rows_modus(_channel(data))
    assert np.array_equal(_bits(out.data), _bits(data))


def test_modus_no_valid_sample_fallback() -> None:
    data = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    mask = np.zeros_like(data)
    out = gwyddion_align_rows_modus(_channel(data), mask=mask,
                                   mask_mode="include")
    # no samples -> global median 0.0 fallback -> shifts 0 -> no change
    assert np.array_equal(_bits(out.data), _bits(data))


def test_modus_masking_mode_discrimination() -> None:
    # bimodal rows: a 10-sample low population with a per-row offset and a
    # 6-sample high population; zero-levelling preserves the different
    # per-row modus estimates of each mask mode
    rows = [
        np.array([5.0 + 10.0 * i] * 10 + [100.0 + 3.0 * i + j for j in range(6)])
        for i in range(4)
    ]
    data = np.stack(rows)
    mask = (data > 50.0).astype(float)
    ignore = gwyddion_align_rows_modus(_channel(data), mask=mask,
                                      mask_mode="ignore")
    include = gwyddion_align_rows_modus(_channel(data), mask=mask,
                                       mask_mode="include")
    exclude = gwyddion_align_rows_modus(_channel(data), mask=mask,
                                       mask_mode="exclude")
    # ignore equals no-mask behaviour; include differs from it here (the
    # masked high population has fewer than 9 samples -> upper median)
    plain = gwyddion_align_rows_modus(_channel(data))
    assert np.array_equal(_bits(ignore.data), _bits(plain.data))
    assert not np.array_equal(_bits(include.data), _bits(plain.data))
    assert not np.array_equal(_bits(include.data), _bits(exclude.data))


# ---------------------------------------------------------------------------
# MATCH
# ---------------------------------------------------------------------------

def test_match_identical_rows() -> None:
    data = np.tile(np.arange(16, dtype=float), (5, 1))
    out = gwyddion_align_rows_match(_channel(data))
    assert np.array_equal(_bits(out.data), _bits(data))


def test_match_pure_offset_zero_weight_guard() -> None:
    data = np.tile(np.arange(16, dtype=float), (5, 1))
    data[3] += 5.0  # pure vertical offset, identical shape
    out = gwyddion_align_rows_match(_channel(data))
    # the source leaves pure offsets uncorrected (zero-weight guard)
    assert np.array_equal(_bits(out.data), _bits(data))


def test_match_active_shape_dependent_correction() -> None:
    base = np.arange(16, dtype=float)
    data = np.stack([base, base.copy()])
    data[1, 8] = 9.0  # shape bump in the second row
    out = gwyddion_align_rows_match(_channel(data))
    assert not np.array_equal(_bits(out.data), _bits(data))


def test_match_sequential_cumulative_correction() -> None:
    base = np.arange(16, dtype=float)
    data = np.stack([base, base.copy(), base.copy(), base.copy()])
    data[1, 8] = 9.0
    data[2, 8] = 9.0
    data[3, 8] = 9.0
    out = gwyddion_align_rows_match(_channel(data))
    assert not np.array_equal(_bits(out.data), _bits(data))


def test_match_alternating_offsets() -> None:
    base = np.arange(16, dtype=float)
    data = np.stack([base, base + 3.0, base, base + 3.0])
    out = gwyddion_align_rows_match(_channel(data))
    # all pure offsets -> zero weight -> no correction
    assert np.array_equal(_bits(out.data), _bits(data))


def test_match_endpoint_inclusion() -> None:
    # mask the whole interior: only endpoints contribute; weights at
    # masked positions are zero, so a pure offset still yields no
    # correction
    base = np.arange(16, dtype=float)
    data = np.stack([base, base + 5.0])
    mask = np.ones_like(data)
    mask[:, 1:-1] = 0.0
    out = gwyddion_align_rows_match(_channel(data), mask=mask,
                                   mask_mode="include")
    assert np.array_equal(_bits(out.data), _bits(data))


def test_match_no_valid_overlap_guard() -> None:
    base = np.arange(16, dtype=float)
    data = np.stack([base, base + 2.0])
    mask = np.zeros_like(data)
    mask[0] = 1.0  # only row 0 masked in -> no valid overlap under include
    out = gwyddion_align_rows_match(_channel(data), mask=mask,
                                   mask_mode="include")
    assert np.array_equal(_bits(out.data), _bits(data))


def test_match_yres_one() -> None:
    data = np.arange(16, dtype=float).reshape(1, 16)
    out = gwyddion_align_rows_match(_channel(data))
    assert np.array_equal(_bits(out.data), _bits(data))


def test_match_yres_two() -> None:
    base = np.arange(16, dtype=float)
    data = np.stack([base, base + 1.0])
    data[1, 8] = 8.0  # bump -> shape mismatch activates matching
    out = gwyddion_align_rows_match(_channel(data))
    assert not np.array_equal(_bits(out.data), _bits(data))


def test_match_masking_mode_discrimination() -> None:
    data = np.tile(np.arange(16, dtype=float), (4, 1))
    data[2, 8] = 9.0
    data[3, 8] = 9.0
    mask = np.zeros_like(data)
    mask[:, 4:9] = 1.0
    ignore = gwyddion_align_rows_match(_channel(data), mask=mask,
                                      mask_mode="ignore")
    include = gwyddion_align_rows_match(_channel(data), mask=mask,
                                       mask_mode="include")
    exclude = gwyddion_align_rows_match(_channel(data), mask=mask,
                                       mask_mode="exclude")
    plain = gwyddion_align_rows_match(_channel(data))
    assert np.array_equal(_bits(ignore.data), _bits(plain.data))
    assert not np.array_equal(_bits(include.data), _bits(plain.data))
    assert not np.array_equal(_bits(exclude.data), _bits(plain.data))


def test_match_rejects_xres_one() -> None:
    with pytest.raises(ValueError, match="two columns"):
        gwyddion_align_rows_match(_channel(np.zeros((4, 1))))
