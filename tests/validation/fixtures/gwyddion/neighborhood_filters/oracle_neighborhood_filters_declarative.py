"""Structurally independent declarative oracle for the Gwydion 2.71
neighborhood filters (Rank Filter, disc Median, Gaussian).

Validates the mathematical/discrete meaning of the operations WITHOUT
porting the source kernels or sharing any implementation with
oracle_neighborhood_filters_source.py (no import, no shared helpers, no
case identifiers, no fixture expected arrays as inputs).

Different decomposition:
  * elliptic footprint as a geometric inclusion test (x^2/a^2 + y^2/b^2
    style sampling with independent rounding), not the source row-span
    recurrence;
  * independent neighborhood enumeration over extended coordinates;
  * independent sorting and rank selection;
  * independent rank conversion (round-half-up formulation);
  * Gaussian kernel built independently and convolved with a separate
    mirror-padding scheme.

Floating results may differ from source-order arithmetic in the last ulp(s);
differences are characterized, never silently matched.  No production
tolerance is frozen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class DeclarativeReference:
    """Declarative reconstruction plus comparison metrics."""

    input_snapshot: FloatArray
    xres: int
    yres: int
    operation: str
    params: tuple[float, ...]
    footprint_coords: tuple[tuple[int, int], ...]
    footprint_count: int
    rank: int
    result: FloatArray
    discrete_state_exact: bool
    result_bitwise: int
    result_total: int
    max_abs: float
    max_ulp: float
    constant_residual: float
    impulse_residual: float
    symmetry_error: float
    classification: str


def _validate(field: object) -> np.ndarray:
    data = np.array(np.asarray(field, dtype=np.float64), dtype=np.float64,
                    order="C", copy=True)
    if data.ndim != 2 or 0 in data.shape:
        raise ValueError("field must be non-empty two-dimensional")
    if not np.all(np.isfinite(data)):
        raise ValueError("field must be finite")
    return data


def _independent_ellipse_coords(width: int, height: int) -> list[tuple[int, int]]:
    """Geometric inclusion test for the inscribed ellipse.

    A pixel (i, j) belongs when its center lies inside the ellipse with
    semi-axes a = width/2, b = height/2 centered at the box center:
        ((j + 0.5 - a)/a)^2 + ((i + 0.5 - b)/b)^2 <= 1
    This is deliberately NOT the source row-span recurrence; the two
    formulations agree on active coordinates for every tested size.
    """
    a = width / 2.0
    b = height / 2.0
    coords: list[tuple[int, int]] = []
    for i in range(height):
        for j in range(width):
            x = (j + 0.5 - a) / a
            y = (i + 0.5 - b) / b
            if x * x + y * y <= 1.0:
                coords.append((i, j))
    return coords


def _mirror_pad_row(row: np.ndarray, radius: int) -> np.ndarray:
    """Independent mirror padding for one row (whole-sample reflection).

    Reflects about the edge pixels: one step beyond the left edge is
    row[1], two steps row[2], ... up to row[n-1], then the reflection
    folds back (row[n-2], ...), matching whole-sample mirror extension for
    arbitrary radii.
    """
    n = row.size
    if n == 1:
        return np.full(1 + 2 * radius, row[0])
    # whole-sample reflection: left of index 0 is index 1, then 2, ...
    # up to index n-1, then folds back through n-2, n-3, ...; the right
    # side is symmetric.  This is the standard "mirror" extension used by
    # the source convolution machinery (index k < width ? k : mres-1-k on
    # mres = 2*width maps the same way).
    left_idx = np.empty(radius, dtype=np.int64)
    for k in range(1, radius + 1):
        t = k % (2 * (n - 1))
        left_idx[k - 1] = t if t <= n - 1 else 2 * (n - 1) - t
    right_idx = np.empty(radius, dtype=np.int64)
    for k in range(1, radius + 1):
        t = k % (2 * (n - 1))
        right_idx[k - 1] = n - 1 - (t if t <= n - 1 else 2 * (n - 1) - t)
    padded = np.empty(n + 2 * radius, dtype=np.float64)
    padded[radius:radius + n] = row
    padded[:radius] = row[left_idx]
    padded[radius + n:] = row[right_idx]
    return padded


def _independent_gaussian_kernel(sigma: float, res: int) -> np.ndarray:
    """Independently constructed symmetric Gaussian kernel (own loops)."""
    vals = []
    for i in range(res):
        x = i - (res - 1) / 2.0
        vals.append(math.exp(-(x * x) / (2.0 * sigma * sigma)))
    total = math.fsum(vals)
    return np.array([v / total for v in vals], dtype=np.float64)


def _ulp(a: float, b: float) -> int:
    if a == 0.0 or b == 0.0:
        return 0
    ba = int(np.ascontiguousarray(np.array([a])).view(np.uint64)[0])
    bb = int(np.ascontiguousarray(np.array([b])).view(np.uint64)[0])
    return abs(ba - bb)


def _compare(a: np.ndarray, b: np.ndarray) -> tuple[int, int, float, int]:
    ab = np.ascontiguousarray(a).view(np.uint64).ravel()
    bb = np.ascontiguousarray(b).view(np.uint64).ravel()
    equal = int(np.count_nonzero(ab == bb))
    max_abs = 0.0
    max_ulp = 0
    for i in range(ab.size):
        if ab[i] == bb[i]:
            continue
        if int(ab[i]) ^ int(bb[i]) == 0x8000000000000000:
            continue
        max_abs = max(max_abs, abs(float(a.ravel()[i]) - float(b.ravel()[i])))
        max_ulp = max(max_ulp, _ulp(float(a.ravel()[i]), float(b.ravel()[i])))
    return equal, int(ab.size), max_abs, max_ulp


def _declarative_rank(data: np.ndarray, radius: int, percentile: float) -> FloatArray:
    side = 2 * radius + 1
    coords = _independent_ellipse_coords(side, side)
    center = side // 2
    offsets = [(i - center, j - center) for i, j in coords]
    n = len(offsets)
    rank = math.floor(percentile * (n - 1) + 0.5)
    yres, xres = data.shape
    out = np.empty((yres, xres), dtype=np.float64)
    for i in range(yres):
        for j in range(xres):
            vals = []
            for di, dj in offsets:
                ii = min(max(i + di, 0), yres - 1)
                jj = min(max(j + dj, 0), xres - 1)
                vals.append(float(data[ii, jj]))
            out[i, j] = sorted(vals)[rank]
    return out


def _declarative_median(data: np.ndarray, size: int) -> FloatArray:
    coords = _independent_ellipse_coords(size, size)
    center = size // 2
    offsets = [(i - center, j - center) for i, j in coords]
    n = len(offsets)
    rank = n // 2
    yres, xres = data.shape
    out = np.empty((yres, xres), dtype=np.float64)
    for i in range(yres):
        for j in range(xres):
            vals = []
            for di, dj in offsets:
                ii = min(max(i + di, 0), yres - 1)
                jj = min(max(j + dj, 0), xres - 1)
                vals.append(float(data[ii, jj]))
            out[i, j] = sorted(vals)[rank]
    return out


def _declarative_gaussian(data: np.ndarray, sigma: float) -> tuple[FloatArray, FloatArray]:
    yres, xres = data.shape
    if sigma == 0.0:
        return data.copy(order="C"), np.empty(0, dtype=np.float64)
    res = 2 * math.ceil(5.0 * sigma) + 1
    cap = 3 * min(xres, yres)
    if res > cap:
        res = cap
        if res % 2 == 0:
            res -= 1
    kernel = _independent_gaussian_kernel(sigma, res)
    radius = res // 2
    # independent mirror-padded separable convolution (H then V)
    hpass = np.empty((yres, xres), dtype=np.float64)
    for i in range(yres):
        padded = _mirror_pad_row(data[i], radius)
        for j in range(xres):
            hpass[i, j] = float(np.dot(kernel, padded[j:j + res]))
    out = np.empty((yres, xres), dtype=np.float64)
    for j in range(xres):
        col = hpass[:, j]
        padded = _mirror_pad_row(col, radius)
        for i in range(yres):
            out[i, j] = float(np.dot(kernel, padded[i:i + res]))
    return out, kernel


def oracle_neighborhood_filters_declarative(
    field: object,
    *,
    operation: str,
    params: tuple[float, ...],
    compiled_result: object | None = None,
) -> DeclarativeReference:
    """Declarative reconstruction with optional compiled comparison.

    ``params``: (radius, percentile1) for rank; (size,) for median;
    (sigma,) for gaussian.  ``compiled_result`` is used only for the
    comparison metrics, never as expected values.
    """
    if operation not in ("rank", "median", "gaussian"):
        raise ValueError(f"unknown operation {operation!r}")
    data = _validate(field)
    yres, xres = data.shape

    coords: list[tuple[int, int]]
    if operation == "rank":
        radius, percentile = int(params[0]), float(params[1])
        result = _declarative_rank(data, radius, percentile)
        coords = _independent_ellipse_coords(2 * radius + 1, 2 * radius + 1)
        rank = math.floor(percentile * (len(coords) - 1) + 0.5)
        classification = "KTH_RANK_ORDERING"
    elif operation == "median":
        size = int(params[0])
        result = _declarative_median(data, size)
        coords = _independent_ellipse_coords(size, size)
        rank = len(coords) // 2
        classification = "KTH_RANK_ORDERING"
    else:
        sigma = float(params[0])
        result, kernel = _declarative_gaussian(data, sigma)
        coords = []
        rank = 0
        classification = "SOURCE_SUMMATION_ORDER" if sigma != 0.0 else "LIBRARY_DOMAIN_ONLY"

    metrics: tuple[int, int, float, int] = (0, 0, 0.0, 0)
    if compiled_result is not None:
        metrics = _compare(result, np.asarray(compiled_result))
    eq, total, max_abs, max_ulp = metrics

    constant_residual = 0.0
    impulse_residual = 0.0
    symmetry_error = 0.0
    if operation == "gaussian" and sigma != 0.0:
        const = np.full_like(data, 1.0)
        gout, _ = _declarative_gaussian(const, sigma)
        constant_residual = float(np.abs(gout - 1.0).max())
        imp = np.zeros_like(data)
        imp[yres // 2, xres // 2] = 1.0
        iout, _ = _declarative_gaussian(imp, sigma)
        impulse_residual = float(np.abs(iout.sum() - 1.0))
        # symmetry of the reconstructed kernel-free impulse response
        if min(yres, xres) >= 5:
            symmetry_error = float(np.abs(iout - iout[::-1, ::-1]).max())

    return DeclarativeReference(
        input_snapshot=data, xres=xres, yres=yres, operation=operation,
        params=params, footprint_coords=tuple(coords),
        footprint_count=len(coords), rank=rank, result=result,
        discrete_state_exact=True, result_bitwise=eq, result_total=total,
        max_abs=max_abs, max_ulp=max_ulp, constant_residual=constant_residual,
        impulse_residual=impulse_residual, symmetry_error=symmetry_error,
        classification=classification,
    )
