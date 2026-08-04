"""Private Gwydion 2.71 neighborhood-filter kernels (Rank, disc Median,
Gaussian).

Implements the three A2 neighborhood-filter operations with the exact
arithmetic of the frozen compiled campaign profile:

  COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION

Parity target is the compiled campaign evidence (frozen JSON/NPZ
fixtures).  This module is a standalone production reimplementation of the
independently established mathematical contract; it shares no code with
the validation oracles, contains no case identifiers and reads no
fixtures, source trees or Gwydion runtime.

Frozen semantics reproduced:

  * elliptic footprint row spans (gwy_data_field_elliptic_area_fill):
      s = ((i + 0.5)/b)*(2 - (i + 0.5)/b),  b = height/2;
      jfrom = ceil(a*(1 - sqrt(s)) - 0.5),
      jto   = floor(a*(1 + sqrt(s)) - 0.5),  a = width/2;
  * kth-rank value: the k-th smallest element of the neighborhood
    multiset (the compiled selection returns a stored element, so
    duplicates and signed zeros resolve to the element at the rank);
  * GWY_ROUND(x) = floor(x + 0.5) for percentile -> rank conversion;
  * k=0 -> local minimum, k=n-1 -> local maximum (endpoint dispatch);
  * EXTEND border (nearest-constant extension) for Rank and Median;
  * Gaussian: res = 2*ceil(5*sigma)+1 capped at 3*min(xres,yres) forced
    odd; coefficients exp(-x^2/(2*sigma^2)) with x = i-(res-1)/2;
    sequential-sum normalization via reciprocal multiply (NOT forced to
    exactly 1.0); separable horizontal-then-vertical passes with mirror
    extension; sigma == 0 is the private library-domain no-op.

Source/version attribution (behavioral, no code copied): Gwydion 2.71
modules/process/rank-filter.c, modules/tools/filter.c,
libprocess/filters-minmax.c, libprocess/elliptic.c,
libprocess/filters-convdeconv.c, libgwyd*dion/gwymath-rank.c.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

#: Source GUI parameter ranges.
RANK_RADIUS_MIN = 1
RANK_RADIUS_MAX = 1024
MEDIAN_SIZE_MIN = 2
MEDIAN_SIZE_MAX = 31
GAUSSIAN_SIGMA_MIN = 0.01
GAUSSIAN_SIGMA_MAX = 40.0


def _validated_field(value: object, *, label: str) -> np.ndarray:
    """Validate and copy a finite two-dimensional real numeric field."""
    try:
        source = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"Gwydion neighborhood filter {label} must be "
                        "array-compatible") from exc
    if source.ndim != 2:
        raise ValueError(f"Gwydion neighborhood filter {label} must be "
                         "two-dimensional")
    if 0 in source.shape:
        raise ValueError(f"Gwydion neighborhood filter {label} must have "
                         "non-empty dimensions")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError(f"Gwydion neighborhood filter {label} must contain "
                        "real numeric values")
    values = np.array(source, dtype=np.float64, order="C", copy=True)
    if not np.isfinite(values).all():
        raise ValueError(f"Gwydion neighborhood filter {label} must be finite")
    return values


def _validated_radius(value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, np.integer)):
        raise TypeError("Gwydion rank filter radius must be an integer")
    radius = int(value)
    if not RANK_RADIUS_MIN <= radius <= RANK_RADIUS_MAX:
        raise ValueError("Gwydion rank filter radius must be in "
                         f"{RANK_RADIUS_MIN}..{RANK_RADIUS_MAX}")
    return radius


def _validated_percentile(value: object, *, label: str = "percentile") -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating)):
        raise TypeError(f"Gwydion rank filter {label} must be a real scalar")
    p = float(value)
    if not math.isfinite(p):
        raise ValueError(f"Gwydion rank filter {label} must be finite")
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"Gwydion rank filter {label} must be in 0..1")
    return p


def _validated_median_size(value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, np.integer)):
        raise TypeError("Gwydion median filter size must be an integer")
    size = int(value)
    if not MEDIAN_SIZE_MIN <= size <= MEDIAN_SIZE_MAX:
        raise ValueError("Gwydion median filter size must be in "
                         f"{MEDIAN_SIZE_MIN}..{MEDIAN_SIZE_MAX}")
    return size


def _validated_sigma(value: object, *, public: bool) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating)):
        raise TypeError("Gwydion gaussian filter sigma must be a real scalar")
    sigma = float(value)
    if not math.isfinite(sigma):
        raise ValueError("Gwydion gaussian filter sigma must be finite")
    if public:
        if not GAUSSIAN_SIGMA_MIN <= sigma <= GAUSSIAN_SIGMA_MAX:
            raise ValueError("Gwydion gaussian filter sigma must be in "
                             f"{GAUSSIAN_SIGMA_MIN}..{GAUSSIAN_SIGMA_MAX}")
    elif sigma < 0.0:
        raise ValueError("Gwydion gaussian filter sigma must be "
                         "non-negative")
    return sigma


def _gwy_round(x: float) -> int:
    """GWY_ROUND(x) = floor(x + 0.5)."""
    return math.floor(x + 0.5)


def _kth_value(values: Sequence[float], k: int) -> float:
    """Value at rank k of the sorted multiset (source selection value)."""
    return sorted(values)[k]


# ---------------------------------------------------------------------------
# Elliptic footprint geometry (shared by Rank and Median)
# ---------------------------------------------------------------------------

def _elliptic_spans(width: int, height: int) -> tuple[list[tuple[int | None, int | None]], int]:
    """Exact gwy_data_field_elliptic_area_fill row spans and active count."""
    a = width / 2.0
    b = height / 2.0
    spans: list[tuple[int | None, int | None]] = []
    count = 0
    for i in range(height):
        s = (i + 0.5) / b
        s = s * (2.0 - s)
        if s <= 0.0:
            spans.append((None, None))
            continue
        s = math.sqrt(s)
        jfrom = math.ceil(a * (1.0 - s) - 0.5)
        jto = math.floor(a * (1.0 + s) - 0.5)
        jfrom = max(jfrom, 0)
        jto = min(jto, width - 1)
        spans.append((jfrom, jto))
        if jto >= jfrom:
            count += jto - jfrom + 1
    return spans, count


def _elliptic_offsets(side: int) -> tuple[list[tuple[int, int]], int, int]:
    """(offsets, center, count) for the inscribed ellipse.

    Center is side//2 (the source anchors the kernel at kxres/2), which
    equals (side-1)//2 for odd sides and one lower-right for even sides.
    """
    spans, count = _elliptic_spans(side, side)
    center = side // 2
    offsets: list[tuple[int, int]] = []
    for i in range(side):
        f, t = spans[i]
        if f is None or t is None or t < f:
            continue
        for j in range(f, t + 1):
            offsets.append((i - center, j - center))
    return offsets, center, count


def _extend_gather(field: FloatArray, i: int, j: int,
                   offsets: Sequence[tuple[int, int]]) -> list[float]:
    """Gather neighborhood values with EXTEND (nearest-constant) borders."""
    yres, xres = field.shape
    values: list[float] = []
    for di, dj in offsets:
        ii = i + di
        jj = j + dj
        if ii < 0:
            ii = 0
        elif ii >= yres:
            ii = yres - 1
        if jj < 0:
            jj = 0
        elif jj >= xres:
            jj = xres - 1
        values.append(float(field[ii, jj]))
    return values


def _apply_rank_kernel(field: FloatArray, offsets: Sequence[tuple[int, int]],
                       rank: int) -> np.ndarray:
    yres, xres = field.shape
    out = np.empty((yres, xres), dtype=np.float64)
    for i in range(yres):
        for j in range(xres):
            vals = _extend_gather(field, i, j, offsets)
            out[i, j] = _kth_value(vals, rank)
    return out


# ---------------------------------------------------------------------------
# Rank filter
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GwydionRankFilterResult:
    """Immutable private Rank result with all source output modes."""

    input_snapshot: FloatArray
    xres: int
    yres: int
    radius: int
    footprint_side: int
    footprint_count: int
    footprint_spans: tuple[tuple[int | None, int | None], ...]
    percentile1: float
    percentile2: float | None
    rank1: int
    rank2: int | None
    both: bool
    difference: bool
    result: FloatArray
    result2: FloatArray | None
    difference_result: FloatArray | None
    delta1: FloatArray
    delta2: FloatArray | None
    input_mutation_evidence: bool


def _gwydion_rank_filter(
    field: object,
    *,
    radius: object,
    percentile: object,
    percentile2: object | None = None,
    both: bool = False,
    difference: bool = False,
) -> GwydionRankFilterResult:
    """Private Rank kernel supporting primary, secondary, both and
    difference source output modes."""
    data = _validated_field(field, label="data")
    yres, xres = data.shape
    radius_v = _validated_radius(radius)
    p1 = _validated_percentile(percentile, label="percentile")
    p2: float | None = None
    if percentile2 is not None:
        p2 = _validated_percentile(percentile2, label="percentile2")

    side = 2 * radius_v + 1
    offsets, _center, n = _elliptic_offsets(side)
    rank1 = _gwy_round(p1 * (n - 1))
    if not 0 <= rank1 < n:
        raise ValueError("Gwydion rank filter rank out of range")

    result = _apply_rank_kernel(data, offsets, rank1)
    delta1 = result - data
    result2: FloatArray | None = None
    delta2: FloatArray | None = None
    rank2: int | None = None
    diff_result: FloatArray | None = None
    if both:
        if p2 is None:
            raise ValueError("Gwydion rank filter both requires percentile2")
        rank2 = _gwy_round(p2 * (n - 1))
        if not 0 <= rank2 < n:
            raise ValueError("Gwydion rank filter rank2 out of range")
        result2 = _apply_rank_kernel(data, offsets, rank2)
        delta2 = result2 - data
        if difference:
            # source in-place subtract: result = result1 - result2
            diff_result = result - result2
            result = diff_result

    return GwydionRankFilterResult(
        input_snapshot=data, xres=xres, yres=yres, radius=radius_v,
        footprint_side=side, footprint_count=n,
        footprint_spans=tuple(_elliptic_spans(side, side)[0]),
        percentile1=p1, percentile2=p2, rank1=rank1, rank2=rank2,
        both=both, difference=difference, result=result, result2=result2,
        difference_result=diff_result, delta1=delta1, delta2=delta2,
        input_mutation_evidence=True,
    )


# ---------------------------------------------------------------------------
# Disc median
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GwydionMedianFilterResult:
    """Immutable private disc-Median result."""

    input_snapshot: FloatArray
    xres: int
    yres: int
    size: int
    footprint_count: int
    footprint_spans: tuple[tuple[int | None, int | None], ...]
    rank: int
    result: FloatArray
    delta: FloatArray
    input_mutation_evidence: bool


def _gwydion_median_filter(field: object, *, size: object) -> GwydionMedianFilterResult:
    """Private disc-Median kernel.

    ``size`` is the footprint SIDE (2..31); even sizes are valid.  The
    median rank is n//2 (upper median) and is NOT derived from a
    percentile conversion.
    """
    data = _validated_field(field, label="data")
    yres, xres = data.shape
    size_v = _validated_median_size(size)
    offsets, _center, n = _elliptic_offsets(size_v)
    rank = n // 2
    result = _apply_rank_kernel(data, offsets, rank)
    return GwydionMedianFilterResult(
        input_snapshot=data, xres=xres, yres=yres, size=size_v,
        footprint_count=n, footprint_spans=tuple(_elliptic_spans(size_v, size_v)[0]),
        rank=rank, result=result, delta=result - data,
        input_mutation_evidence=True,
    )


# ---------------------------------------------------------------------------
# Gaussian (separable mirror-border, source arithmetic)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GwydionGaussianFilterResult:
    """Immutable private Gaussian result with the horizontal intermediate."""

    input_snapshot: FloatArray
    xres: int
    yres: int
    sigma: float
    res_requested: int
    res: int
    kernel: FloatArray
    kernel_sum: float
    horizontal: FloatArray
    result: FloatArray
    delta: FloatArray
    input_mutation_evidence: bool


def _mirror_index(k: int, mres: int) -> int:
    """Gwydion mirror mapping: k < width ? k : mres-1-k."""
    return k if k < mres // 2 else mres - 1 - k


def _hconvolve_mirror(row: Sequence[float], kernel: Sequence[float]) -> list[float]:
    """Horizontal pass with the source mirror machinery, including the
    in-place self-referential tail update (gwy_data_field_area_hconvolve).
    """
    width = len(row)
    kres = len(kernel)
    mres = 2 * width
    k0 = (kres // 2 + 1) * mres
    buf = [0.0] * kres
    work = list(row)
    for j in range(kres):
        k = (j - kres // 2 + k0) % mres
        d = row[_mirror_index(k, mres)]
        for kk in range(j + 1):
            buf[kk] += kernel[j - kk] * d
    pos = 0
    for j in range(width):
        work[j] = buf[pos]
        buf[pos] = 0.0
        pos = (pos + 1) % kres
        k = (j + kres - kres // 2 + k0) % mres
        d = work[_mirror_index(k, mres)]
        for kk in range(pos, kres):
            buf[kk] += kernel[kres - 1 - (kk - pos)] * d
        for kk in range(pos):
            buf[kk] += kernel[pos - 1 - kk] * d
    return work


def _gwydion_gaussian_filter(field: object, *, sigma: object,
                             public: bool) -> GwydionGaussianFilterResult:
    """Private Gaussian kernel.

    ``public=True`` enforces the tool sigma range and rejects sigma=0;
    ``public=False`` preserves the library-domain sigma=0 no-op.
    """
    data = _validated_field(field, label="data")
    yres, xres = data.shape
    sigma_v = _validated_sigma(sigma, public=public)

    if sigma_v == 0.0:
        return GwydionGaussianFilterResult(
            input_snapshot=data, xres=xres, yres=yres, sigma=0.0,
            res_requested=0, res=0,
            kernel=np.empty(0, dtype=np.float64), kernel_sum=0.0,
            horizontal=data.copy(order="C"), result=data.copy(order="C"),
            delta=np.zeros_like(data), input_mutation_evidence=True,
        )

    res = 2 * math.ceil(5.0 * sigma_v) + 1
    res_requested = res
    cap = 3 * min(xres, yres)
    if res > cap:
        res = cap
        if res % 2 == 0:
            res -= 1

    kernel_vals: list[float] = []
    for i in range(res):
        x = i - (res - 1) / 2.0
        x /= sigma_v
        kernel_vals.append(math.exp(-x * x / 2.0))
    kernel_sum_raw = 0.0
    for v in kernel_vals:
        kernel_sum_raw += v
    inv = 1.0 / kernel_sum_raw
    kernel_norm = [v * inv for v in kernel_vals]
    kernel_arr = np.array(kernel_norm, dtype=np.float64)
    kernel_sum = 0.0
    for v in kernel_norm:
        kernel_sum += v

    horizontal = np.empty((yres, xres), dtype=np.float64)
    for i in range(yres):
        row = [float(data[i, j]) for j in range(xres)]
        horizontal[i] = _hconvolve_mirror(row, kernel_norm)
    vertical = np.empty((yres, xres), dtype=np.float64)
    for j in range(xres):
        col = [float(horizontal[i, j]) for i in range(yres)]
        out = _hconvolve_mirror(col, kernel_norm)
        for i in range(yres):
            vertical[i, j] = out[i]

    return GwydionGaussianFilterResult(
        input_snapshot=data, xres=xres, yres=yres, sigma=sigma_v,
        res_requested=res_requested, res=res, kernel=kernel_arr,
        kernel_sum=kernel_sum, horizontal=horizontal, result=vertical,
        delta=vertical - data, input_mutation_evidence=True,
    )
