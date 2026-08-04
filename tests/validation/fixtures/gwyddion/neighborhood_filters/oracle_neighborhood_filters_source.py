"""Exact source-semantic Python oracle for the Gwydion 2.71 neighborhood
filters (Rank Filter, disc Median, Gaussian).

Reproduces the frozen compiled-profile numerical contract of:
  * modules/process/rank-filter.c (rank_filter process orchestration),
  * modules/tools/filter.c (Filter Tool median and gaussian branches),
  * libprocess/filters-minmax.c (gwy_data_field_area_filter_kth_rank),
  * libprocess/elliptic.c (gwy_data_field_elliptic_area_fill),
  * libprocess/filters-convdeconv.c (gwy_data_field_area_filter_gaussian,
    gwy_data_field_area_convolve_1d mirror machinery),
  * libgwyd*dion/gwymath-rank.c (gwy_math_kth_rank value semantics),
using only the standard library and NumPy.

Independence: no production imports, no fixture expected-output reads, no
Gwydion calls, no SciPy, no campaign-parser imports, no case identifiers,
no hardcoded expected arrays.

Frozen semantics reproduced bitwise:
  * elliptic footprint row spans:
      s = ((i + 0.5)/b)*(2 - (i + 0.5)/b),  b = height/2;
      jfrom = ceil(a*(1 - sqrt(s)) - 0.5),  jto = floor(a*(1 + sqrt(s)) - 0.5)
      with a = width/2, clamped to the box;
  * kth-rank value: the k-th smallest value of the neighborhood multiset
    (the compiled selection returns a stored element, so duplicates and
    signed zeros resolve to the element at the rank, not a synthesized
    value);
  * GWY_ROUND(x) = floor(x + 0.5) for the percentile->rank conversion;
  * k=0 -> local minimum, k=n-1 -> local maximum (endpoint dispatch);
  * EXTEND border (nearest-constant extension) for rank and median;
  * Gaussian: res = 2*ceil(5*sigma)+1 capped at 3*min(xres,yres) forced
    odd; coefficients exp(-x^2/(2*sigma^2)) with x = i-(res-1)/2;
    sequential-sum normalization (NOT forced to exactly 1.0); separable
    horizontal-then-vertical passes with mirror extension
    (index k < width ? k : mres-1-k on mres = 2*width);
  * sigma == 0 is a library-domain no-op.

The Gaussian constant-field output is not forced to the mathematical
constant: kernel-normalization rounding (~1e-15) is reproduced, not
corrected.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

MAX_RANK_RADIUS = 1024
MAX_TOOL_MEDIAN_SIZE = 31
MIN_TOOL_MEDIAN_SIZE = 2
TOOL_GAUSSIAN_SIGMA_MIN = 0.01
TOOL_GAUSSIAN_SIGMA_MAX = 40.0


def _validated_field(value: object, *, label: str) -> np.ndarray:
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


def _gwy_round(x: float) -> int:
    """GWY_ROUND(x) = floor(x + 0.5)."""
    return math.floor(x + 0.5)


def _seq_sum(values: list[float]) -> float:
    """Sequential left-to-right double summation (source order)."""
    total = 0.0
    for v in values:
        total = total + v
    return total


def _kth_value(values: list[float], k: int) -> float:
    """Value at rank k of the sorted multiset.

    The compiled selection (gwy_math_kth_rank) returns the element that
    lands at rank k after partitioning; that element equals the k-th
    smallest value of the multiset.  For duplicate or signed-zero values
    the returned element's bits are a stored element at that rank.
    """
    ordered = sorted(values)
    return ordered[k]


def elliptic_spans(width: int, height: int) -> tuple[list[tuple[int | None, int | None]], int]:
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


def elliptic_active_coordinates(width: int, height: int) -> list[tuple[int, int]]:
    """Row-major active coordinates of the inscribed ellipse (source order)."""
    spans, _ = elliptic_spans(width, height)
    coords: list[tuple[int, int]] = []
    for i, (f, t) in enumerate(spans):
        if f is not None and t is not None and t >= f:
            for j in range(f, t + 1):
                coords.append((i, j))
    return coords


def _extend_neighbor_values(field: FloatArray, center_i: int, center_j: int,
                            offsets: list[tuple[int, int]]) -> list[float]:
    """Gather neighborhood values with EXTEND (nearest-constant) borders.

    The compiled kth_rank path extends the field by copying edge rows/
    columns: rows above/below use the first/last row, columns left/right
    use the first/last column, corners follow the row/column extension.
    """
    yres, xres = field.shape
    values: list[float] = []
    for di, dj in offsets:
        i = center_i + di
        j = center_j + dj
        if i < 0:
            i = 0
        elif i >= yres:
            i = yres - 1
        if j < 0:
            j = 0
        elif j >= xres:
            j = xres - 1
        values.append(float(field[i, j]))
    return values


@dataclass(frozen=True)
class RankFilterReference:
    """Immutable Rank Filter result with full output-mode diagnostics."""

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


def oracle_rank_filter(field: object, *, radius: int, percentile1: float,
                       percentile2: float | None = None, both: bool = False,
                       difference: bool = False) -> RankFilterReference:
    """Run the exact source-semantic Rank Filter oracle."""
    data = _validated_field(field, label="data")
    yres, xres = data.shape
    if isinstance(radius, (bool, np.bool_)) or not isinstance(radius, (int, np.integer)):
        raise TypeError("Gwydion rank filter radius must be an integer")
    radius = int(radius)
    if not 1 <= radius <= MAX_RANK_RADIUS:
        raise ValueError("Gwydion rank filter radius must be in 1..1024")
    if isinstance(percentile1, (bool, np.bool_)) or not isinstance(
            percentile1, (int, float, np.integer, np.floating)):
        raise TypeError("Gwydion rank filter percentile1 must be a real scalar")
    percentile1 = float(percentile1)
    if not 0.0 <= percentile1 <= 1.0:
        raise ValueError("Gwydion rank filter percentile must be in 0..1")
    percentile2f: float | None = None
    if percentile2 is not None:
        percentile2f = float(percentile2)
        if not 0.0 <= percentile2f <= 1.0:
            raise ValueError("Gwydion rank filter percentile2 must be in 0..1")

    side = 2 * radius + 1
    spans, n = elliptic_spans(side, side)
    center = side // 2
    offsets: list[tuple[int, int]] = []
    for i in range(side):
        f, t = spans[i]
        if f is None or t is None or t < f:
            continue
        for j in range(f, t + 1):
            offsets.append((i - center, j - center))
    rank1 = _gwy_round(percentile1 * (n - 1))
    if not 0 <= rank1 < n:
        raise ValueError("rank1 out of range")

    def apply_kth(rank: int) -> FloatArray:
        out = np.empty((yres, xres), dtype=np.float64)
        for i in range(yres):
            for j in range(xres):
                vals = _extend_neighbor_values(data, i, j, offsets)
                out[i, j] = _kth_value(vals, rank)
        return out

    result = apply_kth(rank1)
    delta1 = result - data
    result2: FloatArray | None = None
    delta2: FloatArray | None = None
    rank2: int | None = None
    diff_result: FloatArray | None = None
    if both:
        if percentile2f is None:
            raise ValueError("both requires percentile2")
        rank2 = _gwy_round(percentile2f * (n - 1))
        if not 0 <= rank2 < n:
            raise ValueError("rank2 out of range")
        result2 = apply_kth(rank2)
        delta2 = result2 - data
        if difference:
            # the source subtracts in place:
            # gwy_data_field_subtract_fields(result, result, result2)
            # so the emitted primary result IS the difference
            diff_result = result - result2
            result = diff_result

    return RankFilterReference(
        input_snapshot=data,
        xres=xres, yres=yres,
        radius=radius, footprint_side=side, footprint_count=n,
        footprint_spans=tuple(spans),
        percentile1=percentile1, percentile2=percentile2f,
        rank1=rank1, rank2=rank2, both=both, difference=difference,
        result=result, result2=result2, difference_result=diff_result,
        delta1=delta1, delta2=delta2,
        input_mutation_evidence=True,
    )


@dataclass(frozen=True)
class MedianFilterReference:
    """Immutable disc-Median result."""

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


def oracle_median_filter(field: object, *, size: int) -> MedianFilterReference:
    """Run the exact source-semantic disc-Median oracle.

    ``size`` is the footprint SIDE (Filter Tool parameter), 2..31; even
    sizes are valid.  It is NOT translated to a radius.
    """
    data = _validated_field(field, label="data")
    yres, xres = data.shape
    if isinstance(size, (bool, np.bool_)) or not isinstance(size, (int, np.integer)):
        raise TypeError("Gwydion median filter size must be an integer")
    size = int(size)
    if not MIN_TOOL_MEDIAN_SIZE <= size <= MAX_TOOL_MEDIAN_SIZE:
        raise ValueError("Gwydion median filter size must be in 2..31")

    spans, n = elliptic_spans(size, size)
    # crop_extend_field_for_kernel anchors the kernel at kxres/2 (integer
    # division), so the neighborhood center is size//2 for both odd and
    # even sizes (for odd sizes size//2 == (size-1)//2; for even sizes it
    # is one column/row lower-right, matching the compiled EXTEND profile)
    center = size // 2
    offsets: list[tuple[int, int]] = []
    for i in range(size):
        f, t = spans[i]
        if f is None or t is None or t < f:
            continue
        for j in range(f, t + 1):
            offsets.append((i - center, j - center))
    rank = n // 2
    result = np.empty((yres, xres), dtype=np.float64)
    for i in range(yres):
        for j in range(xres):
            vals = _extend_neighbor_values(data, i, j, offsets)
            result[i, j] = _kth_value(vals, rank)
    return MedianFilterReference(
        input_snapshot=data, xres=xres, yres=yres, size=size,
        footprint_count=n, footprint_spans=tuple(spans), rank=rank,
        result=result, delta=result - data,
        input_mutation_evidence=True,
    )


def _mirror_index(k: int, mres: int) -> int:
    """Gwydion mirror extension: k < width ? k : mres-1-k."""
    return k if k < mres // 2 else mres - 1 - k


def _convolve_1d_mirror(row: list[float], kernel: list[float]) -> list[float]:
    """One horizontal pass with the source mirror machinery, including the
    in-place self-referential tail update.

    Implements gwy_data_field_area_hconvolve for a single row: mres =
    2*width, k0 = (kres/2 + 1)*mres, index k = (j - kres/2 + k0) % mres,
    d = row[k < width ? k : mres-1-k].  The C kernel writes drow[j] in
    place and the tail reads d from drow, so later lookups see already
    computed output values; this oracle mutates a working copy in place to
    reproduce that exact arithmetic.
    """
    width = len(row)
    kres = len(kernel)
    mres = 2 * width
    k0 = (kres // 2 + 1) * mres
    buf = [0.0] * kres
    work = list(row)
    # Initialize with triangular sums, mirror-extend (reads original row)
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


@dataclass(frozen=True)
class GaussianFilterReference:
    """Immutable Gaussian result with the horizontal intermediate."""

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


def oracle_gaussian_filter(field: object, *, sigma: float) -> GaussianFilterReference:
    """Run the exact source-semantic Gaussian oracle.

    sigma == 0 is the library-domain no-op (result == input).  sigma > 0
    follows the tool/library contract with the dimension cap and forced
    odd resolution, sequential-sum kernel normalization, mirror borders,
    and horizontal-then-vertical pass order.
    """
    data = _validated_field(field, label="data")
    yres, xres = data.shape
    if isinstance(sigma, (bool, np.bool_)) or not isinstance(
            sigma, (int, float, np.integer, np.floating)):
        raise TypeError("Gwydion gaussian sigma must be a real scalar")
    sigma = float(sigma)
    if not math.isfinite(sigma):
        raise ValueError("Gwydion gaussian sigma must be finite")
    if sigma < 0.0:
        raise ValueError("Gwydion gaussian sigma must be non-negative")

    if sigma == 0.0:
        return GaussianFilterReference(
            input_snapshot=data, xres=xres, yres=yres, sigma=0.0,
            res_requested=0, res=0,
            kernel=np.empty(0, dtype=np.float64), kernel_sum=0.0,
            horizontal=data.copy(order="C"), result=data.copy(order="C"),
            delta=np.zeros_like(data), input_mutation_evidence=True,
        )

    res = 2 * math.ceil(5.0 * sigma) + 1
    res_requested = res
    cap = 3 * min(xres, yres)
    if res > cap:
        res = cap
        if res % 2 == 0:
            res -= 1
    # kernel coefficients
    kernel_vals: list[float] = []
    for i in range(res):
        x = i - (res - 1) / 2.0
        x /= sigma
        kernel_vals.append(math.exp(-x * x / 2.0))
    kernel_sum_raw = _seq_sum(kernel_vals)
    # gwy_data_line_multiply(kernel, 1.0/sum) computes the reciprocal once
    # and multiplies every element by it (data[i] *= value); multiplying
    # by the reciprocal is NOT bitwise equal to dividing each element.
    inv = 1.0 / kernel_sum_raw
    kernel_norm = [v * inv for v in kernel_vals]
    kernel_arr = np.array(kernel_norm, dtype=np.float64)
    # the emitted kernel_sum is the sequential sum of the NORMALIZED
    # kernel (the probe reads it after gwy_data_line_multiply)
    kernel_sum = _seq_sum(kernel_norm)

    # horizontal pass on every row
    horizontal = np.empty((yres, xres), dtype=np.float64)
    for i in range(yres):
        row = [float(data[i, j]) for j in range(xres)]
        horizontal[i] = _convolve_1d_mirror(row, kernel_norm)
    # vertical pass: transpose, horizontal machinery, transpose back
    vertical = np.empty((yres, xres), dtype=np.float64)
    for j in range(xres):
        col = [float(horizontal[i, j]) for i in range(yres)]
        out = _convolve_1d_mirror(col, kernel_norm)
        for i in range(yres):
            vertical[i, j] = out[i]
    return GaussianFilterReference(
        input_snapshot=data, xres=xres, yres=yres, sigma=sigma,
        res_requested=res_requested, res=res,
        kernel=kernel_arr, kernel_sum=kernel_sum,
        horizontal=horizontal, result=vertical, delta=vertical - data,
        input_mutation_evidence=True,
    )
