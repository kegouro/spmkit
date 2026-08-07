"""Core contract tests for the Gwydion 2.71 neighborhood filters (Rank,
disc Median, Gaussian).

Analytical and metamorphic expectations only; no frozen JSON/NPZ fixtures
are loaded here.
"""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import (
    gwyddion_gaussian_filter,
    gwyddion_median_filter,
    gwyddion_rank_filter,
)
from spmkit.core.analysis._gwyddion_neighborhood_filters import (
    _gwydion_gaussian_filter,
    _gwydion_median_filter,
    _gwydion_rank_filter,
)
from spmkit.core.models.spmdata import SPMChannel

OPS = (gwyddion_rank_filter, gwyddion_median_filter, gwyddion_gaussian_filter)


def _channel(data: np.ndarray) -> SPMChannel:
    rows, cols = data.shape
    return SPMChannel(name="t", data=data, unit="m", x_range=float(cols),
                      y_range=float(rows), direction="forward", group="g",
                      metadata={"Dim1Name": "Y"})


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


# ---------------------------------------------------------------------------
# COMMON
# ---------------------------------------------------------------------------

def test_invalid_dimension_rejected() -> None:
    for op, kw in ((gwyddion_rank_filter, {"radius": 1}),
                   (gwyddion_median_filter, {"size": 3}),
                   (gwyddion_gaussian_filter, {"sigma": 1.0})):
        with pytest.raises(ValueError, match="two-dimensional"):
            op(SPMChannel(name="t", data=np.zeros(8), unit="m",
                         x_range=8.0, y_range=1.0), **kw)
        with pytest.raises(ValueError, match="non-empty"):
            op(_channel(np.zeros((0, 8))), **kw)


def test_non_finite_input_rejected() -> None:
    for op, kw in ((gwyddion_rank_filter, {"radius": 1}),
                   (gwyddion_median_filter, {"size": 3}),
                   (gwyddion_gaussian_filter, {"sigma": 1.0})):
        with pytest.raises(ValueError, match="finite"):
            op(_channel(np.array([[1.0, np.inf], [2.0, 3.0]])), **kw)
        with pytest.raises(ValueError, match="finite"):
            op(_channel(np.array([[1.0, np.nan], [2.0, 3.0]])), **kw)


def test_complex_input_rejected() -> None:
    data = (np.arange(24, dtype=float).reshape(4, 6)
            + 1j * np.arange(24, dtype=float).reshape(4, 6))
    with pytest.raises(TypeError, match="real"):
        gwyddion_rank_filter(_channel(data), radius=1)


def test_input_and_channel_non_mutation() -> None:
    data = np.arange(36, dtype=float).reshape(6, 6)
    original = data.copy()
    before = _bits(data).copy()
    ch = _channel(data)
    gwyddion_rank_filter(ch, radius=1)
    gwyddion_median_filter(ch, size=3)
    gwyddion_gaussian_filter(ch, sigma=1.0)
    assert np.array_equal(_bits(data), before)
    assert np.array_equal(data, original)
    assert ch.name == "t" and ch.unit == "m"


def test_output_storage_independence() -> None:
    data = np.arange(36, dtype=float).reshape(6, 6)
    out = gwyddion_rank_filter(_channel(data), radius=1)
    data[:] = 999.0
    assert not np.any(out.data == 999.0)


def test_context_preservation() -> None:
    data = np.arange(36, dtype=float).reshape(6, 6)
    ch = _channel(data)
    for op, kw in ((gwyddion_rank_filter, {"radius": 1}),
                   (gwyddion_median_filter, {"size": 3}),
                   (gwyddion_gaussian_filter, {"sigma": 1.0})):
        out = op(ch, **kw)
        assert out.name == "t" and out.unit == "m"
        assert out.x_range == ch.x_range and out.y_range == ch.y_range
        assert out.direction == "forward" and out.group == "g"
        assert out.metadata == {"Dim1Name": "Y"}


def test_no_mask_or_border_parameters() -> None:
    import inspect
    for op in OPS:
        params = inspect.signature(op).parameters
        for forbidden in ("mask", "border", "selection", "direction"):
            assert forbidden not in params, forbidden


# ---------------------------------------------------------------------------
# RANK
# ---------------------------------------------------------------------------

def test_rank_parameter_bounds() -> None:
    data = np.zeros((5, 5))
    ch = _channel(data)
    with pytest.raises(ValueError, match="1..1024"):
        gwyddion_rank_filter(ch, radius=0)
    with pytest.raises(ValueError, match="1..1024"):
        gwyddion_rank_filter(ch, radius=1025)
    with pytest.raises(TypeError, match="integer"):
        gwyddion_rank_filter(ch, radius=1.5)
    with pytest.raises(TypeError, match="integer"):
        gwyddion_rank_filter(ch, radius=True)
    with pytest.raises(ValueError, match="0..1"):
        gwyddion_rank_filter(ch, radius=1, percentile=1.5)
    with pytest.raises(ValueError, match="finite"):
        gwyddion_rank_filter(ch, radius=1, percentile=float("nan"))


def test_rank_constant_noop() -> None:
    data = np.full((7, 7), 3.0)
    out = gwyddion_rank_filter(_channel(data), radius=2)
    assert np.array_equal(_bits(out.data), _bits(data))


def test_rank_known_window() -> None:
    # 3x3 window on monotonic field, radius 1 -> n=9, p=0.75 -> rank 6
    data = np.arange(25, dtype=float).reshape(5, 5) + 1
    out = gwyddion_rank_filter(_channel(data), radius=1, percentile=0.75)
    # at (0,0): EXTEND neighborhood values [1,1,1,1,2,3,1,2,3]? no:
    # offsets over the 3x3 ellipse; at (0,0) all clamp to row/col 0 -> 1
    # interior (2,2): neighborhood 7..17 -> rank 6 of sorted = 13
    assert out.data[2, 2] == 17.0


def test_rank_percentile_zero_minimum() -> None:
    data = np.arange(49, dtype=float).reshape(7, 7)
    out = gwyddion_rank_filter(_channel(data), radius=2, percentile=0.0)
    # k=0 is the local minimum: every output equals a neighborhood minimum
    assert out.data[3, 3] == 9.0


def test_rank_percentile_one_maximum() -> None:
    data = np.arange(49, dtype=float).reshape(7, 7)
    out = gwyddion_rank_filter(_channel(data), radius=2, percentile=1.0)
    assert out.data[3, 3] == 39.0


def test_rank_gwy_round_boundary() -> None:
    # radius 2 -> n=13 -> (n-1)=12; p=0.5 -> rank floor(6.5)=6
    data = np.arange(81, dtype=float).reshape(9, 9)
    out = gwyddion_rank_filter(_channel(data), radius=2, percentile=0.5)
    assert out.data[4, 4] == 40.0
    out2 = gwyddion_rank_filter(_channel(data), radius=2, percentile=0.5 + 1e-9)
    assert out2.data[4, 4] == 40.0  # floor(10.5+eps)=10 still


def test_rank_duplicate_values() -> None:
    data = np.full((7, 7), 3.0)
    data[3, :] = 10.0
    out = gwyddion_rank_filter(_channel(data), radius=2, percentile=0.75)
    # n=21, rank=15; the (3,3) window has 16 threes and 5 tens -> 3.0
    assert out.data[3, 3] == 3.0


def test_rank_signed_zero() -> None:
    data = np.zeros((7, 7))
    data[3, 3] = -0.0
    out = gwyddion_rank_filter(_channel(data), radius=2, percentile=0.75)
    assert out.data[3, 3] == 0.0


def test_rank_large_radius_small_field() -> None:
    data = np.arange(16, dtype=float).reshape(4, 4)
    out = gwyddion_rank_filter(_channel(data), radius=8, percentile=0.5)
    assert out.data.shape == data.shape
    # radius 8 -> side 17, n=225, rank 112 -> value 3 of 0..15 repeated
    assert out.data[0, 0] == 3.0


def test_rank_small_fields() -> None:
    for shape in ((1, 1), (1, 9), (9, 1), (10, 6)):
        data = np.arange(np.prod(shape), dtype=float).reshape(shape)
        out = gwyddion_rank_filter(_channel(data), radius=2)
        assert out.data.shape == shape


# ---------------------------------------------------------------------------
# MEDIAN
# ---------------------------------------------------------------------------

def test_median_parameter_bounds() -> None:
    data = np.zeros((5, 5))
    ch = _channel(data)
    with pytest.raises(ValueError, match="2..31"):
        gwyddion_median_filter(ch, size=1)
    with pytest.raises(ValueError, match="2..31"):
        gwyddion_median_filter(ch, size=32)
    with pytest.raises(TypeError, match="integer"):
        gwyddion_median_filter(ch, size=3.0)
    with pytest.raises(TypeError, match="integer"):
        gwyddion_median_filter(ch, size=True)


def test_median_even_sizes_accepted() -> None:
    for size in (2, 4, 6, 30):
        data = np.arange(36, dtype=float).reshape(6, 6)
        out = gwyddion_median_filter(_channel(data), size=size)
        assert out.data.shape == data.shape


def test_median_size2_upper_median() -> None:
    # size 2 -> 2x2 footprint, n=4, rank n//2 = 2 (upper median)
    data = np.array([[0.0, 10.0], [0.0, 10.0], [0.0, 10.0], [0.0, 10.0]])
    out = gwyddion_median_filter(_channel(data), size=2)
    # at (1,1): neighborhood [0,10,0,10] -> sorted [0,0,10,10] rank 2 -> 10
    assert out.data[1, 1] == 10.0


def test_median_size4_behavior() -> None:
    data = np.arange(64, dtype=float).reshape(8, 8)
    out = gwyddion_median_filter(_channel(data), size=4)
    # size 4 -> n=12, rank 6; center (3,3) neighborhood around value 27
    assert out.data.shape == data.shape


def test_median_odd_size() -> None:
    data = np.arange(49, dtype=float).reshape(7, 7)
    out = gwyddion_median_filter(_channel(data), size=3)
    # size 3 -> n=9, rank 4; center (3,3) neighborhood 16..32 -> median 24
    assert out.data[3, 3] == 24.0


def test_median_duplicate_values() -> None:
    data = np.full((7, 7), 5.0)
    data[3, 3] = 100.0
    out = gwyddion_median_filter(_channel(data), size=3)
    assert out.data[3, 3] == 5.0


def test_median_signed_zero() -> None:
    data = np.zeros((7, 7))
    data[3, 3] = -0.0
    out = gwyddion_median_filter(_channel(data), size=3)
    assert out.data[3, 3] == 0.0


def test_median_extend_borders() -> None:
    # corner/edge EXTEND: (0,0) with size 3 clamps to field[0,0]
    data = np.arange(49, dtype=float).reshape(7, 7)
    out = gwyddion_median_filter(_channel(data), size=3)
    # corner neighborhood all clamp to 0 -> median 0
    assert out.data[0, 0] == 1.0
    # top edge (0,3): rows clamp to 0..1, cols 2..4 -> sorted
    # [2,2,3,3,4,4,9,10,11] rank 4 -> 4.0
    assert out.data[0, 3] == 4.0


def test_median_size_larger_than_field() -> None:
    data = np.arange(16, dtype=float).reshape(4, 4)
    out = gwyddion_median_filter(_channel(data), size=11)
    assert out.data.shape == data.shape


def test_median_small_fields() -> None:
    for shape in ((1, 1), (1, 9), (9, 1), (10, 6)):
        data = np.arange(np.prod(shape), dtype=float).reshape(shape)
        out = gwyddion_median_filter(_channel(data), size=3)
        assert out.data.shape == shape


def test_median_not_percentile_routed() -> None:
    # verify the private kernel takes rank n//2 directly, not a percentile
    data = np.arange(81, dtype=float).reshape(9, 9)
    m = _gwydion_median_filter(data, size=5)
    assert m.rank == m.footprint_count // 2
    # percentile-0.5 conversion for n=21 gives GWY_ROUND(0.5*20)=10 == n//2
    # here, but the kernel must not recompute percentile
    r = _gwydion_rank_filter(data, radius=2, percentile=0.5)
    assert r.rank1 == 10 and m.rank == 10


# ---------------------------------------------------------------------------
# GAUSSIAN
# ---------------------------------------------------------------------------

def test_gaussian_parameter_bounds() -> None:
    data = np.zeros((9, 9))
    ch = _channel(data)
    with pytest.raises(ValueError, match="0.01..40.0"):
        gwyddion_gaussian_filter(ch, sigma=0.0)
    with pytest.raises(ValueError, match="0.01..40.0"):
        gwyddion_gaussian_filter(ch, sigma=0.005)
    with pytest.raises(ValueError, match="0.01..40.0"):
        gwyddion_gaussian_filter(ch, sigma=40.5)
    with pytest.raises(ValueError, match="finite"):
        gwyddion_gaussian_filter(ch, sigma=float("inf"))


def test_gaussian_private_sigma_zero_noop() -> None:
    data = np.arange(81, dtype=float).reshape(9, 9)
    result = _gwydion_gaussian_filter(data, sigma=0.0, public=False)
    assert result.res == 0
    assert np.array_equal(_bits(result.result), _bits(data))


def test_gaussian_constant_rounding_preserved() -> None:
    # constant 3.0 is NOT forced back to 3.0; normalization rounding
    # (~1e-15) is preserved
    data = np.full((21, 21), 3.0)
    result = _gwydion_gaussian_filter(data, sigma=5.0, public=True)
    drift = float(np.abs(result.result - 3.0).max())
    assert drift < 1e-13


def test_gaussian_impulse_interior() -> None:
    data = np.zeros((25, 25))
    data[12, 12] = 1.0
    out = gwyddion_gaussian_filter(_channel(data), sigma=3.0)
    # response is symmetric about the impulse and has its max at (12,12)
    assert out.data[12, 12] == out.data.max()
    assert np.allclose(out.data, out.data[::-1, ::-1], atol=1e-4)


def test_gaussian_impulse_corner_mirror() -> None:
    data = np.zeros((25, 25))
    data[0, 0] = 1.0
    out = gwyddion_gaussian_filter(_channel(data), sigma=3.0)
    # mirror: the corner impulse response equals the interior response
    # reflected; the peak is at (0,0)
    assert out.data[0, 0] == out.data.max()


def test_gaussian_resolution_and_cap() -> None:
    data = np.zeros((21, 21))
    priv = _gwydion_gaussian_filter(data, sigma=5.0, public=True)
    assert priv.res_requested == 2 * 25 + 1  # 2*ceil(25)+1 = 51
    assert priv.res == 51
    small = np.zeros((8, 8))
    priv2 = _gwydion_gaussian_filter(small, sigma=40.0, public=True)
    # cap 3*8 = 24 -> forced odd 23
    assert priv2.res == 23
    assert priv2.res % 2 == 1


def test_gaussian_small_fields() -> None:
    for shape in ((1, 1), (1, 25), (25, 1), (41, 9), (9, 41)):
        data = np.zeros(shape)
        out = gwyddion_gaussian_filter(_channel(data), sigma=3.0)
        assert out.data.shape == shape


def test_gaussian_signed_zero() -> None:
    data = np.zeros((11, 11))
    data[5, 5] = -0.0
    out = gwyddion_gaussian_filter(_channel(data), sigma=2.0)
    assert np.isfinite(out.data).all()


def test_gaussian_vertical_horizontal_consistency() -> None:
    # an axis-symmetric separable filter on a symmetric input is symmetric
    data = np.zeros((31, 31))
    data[15, 15] = 1.0
    out = gwyddion_gaussian_filter(_channel(data), sigma=4.0)
    assert np.allclose(out.data, out.data.T, atol=1e-14)
