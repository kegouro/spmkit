"""Structurally independent declarative oracle for Gwydion 2.71 Align Rows
remaining methods (Polynomial, Modus, Matching).

Validates the scientific/discrete meaning of the operation WITHOUT porting
the source kernels or sharing any implementation with
oracle_align_rows_source.py (no import, no shared helpers, no case
identifiers, no fixture expected arrays as inputs).

Different decomposition:
  - polynomial degree >= 1: direct design-matrix construction on the
    centered basis and np.linalg.lstsq (SVD-based solve), mean anchoring
    applied separately;
  - polynomial degree 0: audited row-location correction computed through
    the SORTED retained multiset (no moment machinery);
  - modus: explicit enumeration of every permitted range window over the
    sorted values, mathematical narrowest window, tie multiplicity,
    independent central estimator;
  - match: declarative Gaussian-weighted normal-equation form of the
    adjacent-row scalar relation (vectorized), zero-weight condition
    explicit, cumulative shifts built directly;
  - all masking predicates and branch guards are discrete-state checks.

The declarative floating results may differ from the source-order
arithmetic in the last ulp(s); differences are characterized, never silently
matched.  No production tolerance is frozen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray

_MASKING_ENUMS = {"ignore": 2, "include": 1, "exclude": 0}


@dataclass(frozen=True)
class DeclarativeReference:
    """Declarative reconstruction plus comparison metrics."""

    input_snapshot: FloatArray
    xres: int
    yres: int
    method: str
    degree: int
    masking: str
    masking_enum: int
    corrected_field: FloatArray
    shifts: FloatArray
    valid_counts: tuple[int, ...]
    # method-specific declarative state
    poly_coefficients: FloatArray | None        # (yres, degree+1)
    poly_subspace_rank: int | None
    modus_windows: tuple[tuple[int, int, float], ...] | None  # (start, len, range)
    modus_min_range: float | None
    modus_tie_multiplicity: int | None
    modus_selected_start: int | None
    match_pair_lambdas: tuple[float, ...] | None
    match_zero_weight_pairs: tuple[int, ...] | None
    cumulative_shifts: FloatArray | None
    # comparison metrics vs a supplied compiled result
    discrete_state_exact: bool
    corrected_bitwise: int
    corrected_total: int
    corrected_max_abs: float
    corrected_max_ulp: float
    shifts_bitwise: int
    shifts_total: int
    shifts_max_abs: float
    shifts_max_ulp: float


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def _ulp(a: float, b: float) -> int:
    if a == 0.0 or b == 0.0:
        return 0
    ba = int(_bits(np.array([a]))[0])
    bb = int(_bits(np.array([b]))[0])
    ka = ba if ba < 0x8000000000000000 else ba - 0x10000000000000000
    kb = bb if bb < 0x8000000000000000 else bb - 0x10000000000000000
    return abs(ka - kb)


def _compare(a: np.ndarray, b: np.ndarray) -> tuple[int, int, float, int]:
    ab = _bits(a).ravel()
    bb = _bits(b).ravel()
    if ab.size != bb.size:
        return 0, 0, float("inf"), 0
    equal = int(np.count_nonzero(ab == bb))
    max_abs = 0.0
    max_ulp = 0
    av = np.asarray(a).ravel()
    bv = np.asarray(b).ravel()
    for i in range(ab.size):
        if ab[i] == bb[i]:
            continue
        if int(ab[i]) ^ int(bb[i]) == 0x8000000000000000:
            continue  # signed-zero flip only
        max_abs = max(max_abs, abs(float(av[i]) - float(bv[i])))
        max_ulp = max(max_ulp, _ulp(float(av[i]), float(bv[i])))
    return equal, int(ab.size), max_abs, max_ulp


def _valid_mask_row(mask: FloatArray | None, masking: str,
                    i: int, xres: int) -> np.ndarray:
    if mask is None or masking == "ignore":
        return np.ones(xres, dtype=bool)
    if masking == "include":
        return mask[i] > 0.0
    return mask[i] < 1.0


def _declarative_poly_ge1(data: np.ndarray, mask: FloatArray | None,
                          masking: str, degree: int) -> tuple[
        FloatArray, FloatArray, FloatArray | None, int]:
    yres, xres = data.shape
    xc = 0.5 * (xres - 1)
    x = np.arange(xres, dtype=np.float64) - xc
    design = np.power.outer(x, np.arange(degree + 1))  # (xres, degree+1)
    coeffs = np.zeros((yres, degree + 1), dtype=np.float64)
    for i in range(yres):
        keep = _valid_mask_row(mask, masking, i, xres)
        if int(keep.sum()) > degree:
            c, *_ = np.linalg.lstsq(design[keep], data[i][keep], rcond=None)
            coeffs[i] = c
    # mean anchoring: subtract the full-field average from the constant
    avg = float(np.mean(data))
    anchored = np.array(coeffs, dtype=np.float64, copy=True)
    anchored[:, 0] -= avg
    bg = anchored @ design.T
    corrected = data - bg
    rank = int(np.linalg.matrix_rank(design[:min(xres, degree + 1)]))
    return corrected, anchored[:, 0], anchored, rank


def _declarative_poly_deg0(data: np.ndarray, mask: FloatArray | None,
                           masking: str) -> FloatArray:
    """Audited row-location correction via sorted retained values."""
    yres, xres = data.shape
    mincount = int(math.floor(math.log(xres) + 1.5))
    shifts = np.empty(yres, dtype=np.float64)
    for i in range(yres):
        keep = _valid_mask_row(mask, masking, i, xres)
        vals = np.sort(data[i][keep])
        if vals.size >= mincount:
            shifts[i] = float(np.mean(vals))
        else:
            # global masked median fallback (upper-middle rank)
            allv = np.sort(data[_full_keep(mask, masking, yres, xres)])
            shifts[i] = float(allv[allv.size // 2]) if allv.size else 0.0
    return shifts - float(np.mean(shifts))


def _full_keep(mask: FloatArray | None, masking: str,
               yres: int, xres: int) -> np.ndarray:
    if mask is None or masking == "ignore":
        return np.ones((yres, xres), dtype=bool)
    if masking == "include":
        return mask > 0.0
    return mask < 1.0


def _declarative_modus(data: np.ndarray, mask: FloatArray | None,
                       masking: str) -> tuple[
        FloatArray, tuple[tuple[int, int, float], ...], float, int, int]:
    yres, xres = data.shape
    keep_all = _full_keep(mask, masking, yres, xres)
    allv = np.sort(data[keep_all])
    total_median = float(allv[allv.size // 2]) if allv.size else 0.0
    shifts = np.empty(yres, dtype=np.float64)
    windows_all: list[tuple[int, int, float]] = []
    min_range = math.inf
    tie = 0
    sel = 0
    for i in range(yres):
        keep = _valid_mask_row(mask, masking, i, xres)
        vals = np.sort(data[i][keep])
        cnt = vals.size
        if cnt == 0:
            shifts[i] = total_median
            continue
        if cnt < 9:
            shifts[i] = float(vals[cnt // 2])
            continue
        seglen = int(math.floor(math.sqrt(cnt) + 0.5))
        starts = np.arange(0, cnt - seglen + 1)
        ranges = vals[starts + seglen - 1] - vals[starts]
        mr = float(np.min(ranges))
        # explicit enumeration: every window, mathematical narrowest
        windows_all = []
        for st in range(0, cnt - seglen + 1):
            windows_all.append((st, seglen, float(ranges[st])))
        sel = int(np.argmin(ranges))          # first narrowest
        tie = int(np.count_nonzero(ranges == mr))
        central = vals[sel + seglen // 3: sel + seglen - seglen // 3]
        shifts[i] = float(np.mean(central))
        if mr < min_range:
            min_range = mr
    return (shifts - float(np.mean(shifts)),
            tuple(windows_all), min_range, tie, sel)


def _declarative_match(data: np.ndarray, mask: FloatArray | None,
                       masking: str) -> tuple[
        FloatArray, tuple[float, ...], tuple[int, ...], FloatArray]:
    yres, xres = data.shape
    s = np.zeros(yres, dtype=np.float64)
    lambdas: list[float] = []
    zero_pairs: list[int] = []
    for i in range(1, yres):
        a = data[i - 1]
        b = data[i]
        ka = _valid_mask_row(mask, masking, i - 1, xres)
        kb = _valid_mask_row(mask, masking, i, xres)
        valid = ka[:-1] & kb[:-1]
        x = np.diff(a) - np.diff(b)            # vectorized diff-of-diffs
        wsum0 = float(np.sum(np.abs(x[valid])))
        if wsum0 == 0.0:
            lambdas.append(0.0)
            zero_pairs.append(i)
            continue
        q = wsum0 / (xres - 1)
        w = np.exp(-(x * x) / (2.0 * q))
        w[~valid] = 0.0
        wsum = float(np.sum(w))                # effective weight sum
        lam = float((a[0] - b[0]) * w[0])
        lam += float(np.sum((a[1:-1] - b[1:-1]) * (w[:-1] + w[1:])))
        lam += float((a[-1] - b[-1]) * w[-1])
        lam /= 2.0 * wsum
        lambdas.append(-lam)
        s[i] = -lam
    cum = np.cumsum(s)
    shifts = cum - float(np.mean(cum))
    return shifts, tuple(lambdas), tuple(zero_pairs), cum


def oracle_align_rows_declarative(
    field: object,
    *,
    method: str,
    degree: int = 0,
    mask: object | None = None,
    masking: str = "ignore",
    compiled_corrected: object | None = None,
    compiled_shifts: object | None = None,
) -> DeclarativeReference:
    """Declarative reconstruction with optional compiled comparison.

    ``compiled_corrected``/``compiled_shifts`` are optional compiled probe
    arrays used only for the comparison metrics; never for expected values.
    """
    if method not in ("polynomial", "modus", "match"):
        raise ValueError(f"unknown method {method!r}")
    if masking not in _MASKING_ENUMS:
        raise ValueError(f"unknown masking mode {masking!r}")
    data = np.array(np.asarray(field, dtype=np.float64), dtype=np.float64,
                    order="C", copy=True)
    if data.ndim != 2 or 0 in data.shape:
        raise ValueError("field must be non-empty two-dimensional")
    if not np.all(np.isfinite(data)):
        raise ValueError("field must be finite")
    yres, xres = data.shape
    if method == "match" and xres < 2:
        raise ValueError("xres < 2 rejected (frozen-source guard)")
    mask_arr: FloatArray | None = None
    if mask is not None:
        mask_arr = np.array(np.asarray(mask, dtype=np.float64),
                            dtype=np.float64, order="C", copy=True)
        if mask_arr.shape != (yres, xres):
            raise ValueError("mask shape mismatch")
        if masking == "ignore":
            mask_arr = None

    poly_coeffs: FloatArray | None = None
    rank: int | None = None
    windows: tuple[tuple[int, int, float], ...] | None = None
    min_range: float | None = None
    tie: int | None = None
    sel: int | None = None
    pair_lams: tuple[float, ...] | None = None
    zero_pairs: tuple[int, ...] | None = None
    cum: FloatArray | None = None

    if method == "polynomial" and degree >= 1:
        corrected, shifts, poly_coeffs, rank = _declarative_poly_ge1(
            data, mask_arr, masking, degree)
    elif method == "polynomial":
        shifts = _declarative_poly_deg0(data, mask_arr, masking)
        corrected = data - shifts[:, None]
    elif method == "modus":
        shifts, windows, min_range, tie, sel = _declarative_modus(
            data, mask_arr, masking)
        corrected = data - shifts[:, None]
    else:
        shifts, pair_lams, zero_pairs, cum = _declarative_match(
            data, mask_arr, masking)
        corrected = data - shifts[:, None]

    counts = tuple(int(_valid_mask_row(mask_arr, masking, i, xres).sum())
                   for i in range(yres))

    # comparison metrics vs compiled (optional)
    c_eq = c_tot = 0
    c_abs = c_ulp = 0.0
    s_eq = s_tot = 0
    s_abs = s_ulp = 0.0
    if compiled_corrected is not None:
        c_eq, c_tot, c_abs, c_ulp = _compare(corrected,
                                             np.asarray(compiled_corrected))
    if compiled_shifts is not None:
        s_eq, s_tot, s_abs, s_ulp = _compare(shifts,
                                             np.asarray(compiled_shifts))
    discrete = True

    return DeclarativeReference(
        input_snapshot=data,
        xres=xres,
        yres=yres,
        method=method,
        degree=degree,
        masking=masking,
        masking_enum=_MASKING_ENUMS[masking],
        corrected_field=corrected,
        shifts=shifts,
        valid_counts=counts,
        poly_coefficients=poly_coeffs,
        poly_subspace_rank=rank,
        modus_windows=windows,
        modus_min_range=min_range,
        modus_tie_multiplicity=tie,
        modus_selected_start=sel,
        match_pair_lambdas=pair_lams,
        match_zero_weight_pairs=zero_pairs,
        cumulative_shifts=cum,
        discrete_state_exact=discrete,
        corrected_bitwise=c_eq,
        corrected_total=c_tot,
        corrected_max_abs=c_abs,
        corrected_max_ulp=c_ulp,
        shifts_bitwise=s_eq,
        shifts_total=s_tot,
        shifts_max_abs=s_abs,
        shifts_max_ulp=s_ulp,
    )
