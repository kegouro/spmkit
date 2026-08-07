"""Exact source-semantic Python oracle for Gwydion 2.71 Align Rows
remaining methods (Polynomial, Modus, Matching).

Reproduces the valid frozen-source numerical contract of
modules/process/linematch.c (source-included kernel) plus the linked helper
semantics (libprocess/correct.c, linestats.c, libgwyd*dion/gwymath.c,
gwymath-rank.c) for finite two-dimensional fields, using only the standard
library and NumPy.

Independence: no production imports, no fixture expected-output reads, no
Gwydion calls, no SciPy, no campaign-parser imports, no case identifiers, no
hardcoded expected arrays.

Source facts reproduced exactly (bitwise):
  * masking predicates: INCLUDE keeps mask > 0; EXCLUDE keeps mask < 1 in
    the row-collection loops; the global-median fallback helper
    (area_get_median_mask) uses mask <= 0 for EXCLUDE -- implemented exactly
    as the source does in each place (they coincide for the retained 0/1
    campaign masks);
  * polynomial degree 0 = gwy_data_field_find_row_shifts_trimmed_mean with
    trimfrac 0: per-row means over the collected samples in collection
    order, mincount = GWY_ROUND(log(xres)+1), global masked-median fallback
    for rows below mincount, sequential summation, zero-levelling;
  * polynomial degree >= 1 = gwy_data_field_row_level_poly: full-field mean
    anchoring, per-row moment accumulation with x = j - 0.5*(xres-1),
    lower-triangular packed Cholesky (decompose/solve exact loop order),
    guard xpowers[0] > degree, zeroing otherwise, zxpowers[0] -= avg;
    the Cholesky decompose follows the arithmetic of the INSTALLED
    libgwyd*dion2 2.71 binary (hoisted 1.0/s reciprocal multiply), which
    is what the compiled probe links against; the frozen source text
    (r/s) differs in the last ulp(s) and would not reproduce the compiled
    evidence bitwise;
  * modus: global masked-median fallback; count < 9 -> kth-rank median
    (value at rank count//2); otherwise GWY_ROUND(sqrt(count)) window,
    full sort, first strict minimum of window range, central third
    [seglen/3, seglen - seglen/3) sequential sum;
  * match: adjacent-row diff-of-diffs, |x| diffnorm sum, q = wsum/(xres-1),
    Gaussian weights with the effective weight sum REASSIGNED to the weight
    sum before lambda division, endpoint samples always included, masked
    interior columns skipped, zero-weight guard, cumulative shifts,
    zero-levelling.

Deliberate safe-contract divergences (documented, not silent):
  - non-finite inputs are rejected (finite-input policy);
  - match rejects xres < 2: the frozen source allocates a zero-length weight
    array and reads w[0]/w[xres-2] unconditionally (out-of-bounds for
    xres == 1); no retained campaign case exercises xres == 1.

The kth-rank VALUE (not the partition rearrangement) is what the source
exposes through gwy_math_median; it equals the value at the corresponding
rank of the sorted multiset, so sorted()[k] reproduces it exactly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray

_MASKING_ENUMS = {"ignore": 2, "include": 1, "exclude": 0}


def _gwy_round(x: float) -> int:
    """GWY_ROUND(x) = (gint)floor(x + 0.5)."""
    return int(math.floor(x + 0.5))


def _seq_sum(values: Sequence[float]) -> float:
    """Left-to-right double summation, identical to the C loops."""
    s = 0.0
    for v in values:
        s += v
    return s


def _median_value(values: Sequence[float]) -> float:
    """gwy_math_median(n, a) == value at rank n//2 of the sorted multiset."""
    k = len(values) // 2
    return sorted(values)[k]


def _collected(row: FloatArray, mask_row: FloatArray | None, masking: str,
               xres: int) -> list[float]:
    """Collect the row samples in increasing j order (mask row-loop
    predicate: INCLUDE > 0, EXCLUDE < 1, IGNORE -> all)."""
    out: list[float] = []
    if mask_row is None or masking == "ignore":
        return [float(row[j]) for j in range(xres)]
    if masking == "include":
        for j in range(xres):
            if float(mask_row[j]) > 0.0:
                out.append(float(row[j]))
    else:
        for j in range(xres):
            if float(mask_row[j]) < 1.0:
                out.append(float(row[j]))
    return out


def _median_mask(field: FloatArray, mask: FloatArray | None, masking: str,
                 xres: int, yres: int) -> float:
    """gwy_data_field_area_get_median_mask(0,0,xres,yres) exact semantics.

    EXCLUDE keeps mask <= 0.0 here (source helper), unlike the row loops
    (mask < 1.0); both coincide for the 0/1 campaign masks.
    """
    if mask is None or masking == "ignore":
        return _median_value([float(v) for v in field.ravel()])
    vals: list[float] = []
    if masking == "include":
        for i in range(yres):
            for j in range(xres):
                if float(mask[i, j]) > 0.0:
                    vals.append(float(field[i, j]))
    else:
        for i in range(yres):
            for j in range(xres):
                if float(mask[i, j]) <= 0.0:
                    vals.append(float(field[i, j]))
    if not vals:
        return 0.0
    return _median_value(vals)


def _zero_level(shifts: np.ndarray) -> np.ndarray:
    """zero_level_row_shifts(): shifts += -avg (sequential avg)."""
    avg = _seq_sum([float(v) for v in shifts]) / float(shifts.size)
    return shifts + (-avg)


def _subtract_row_shifts(field: FloatArray, shifts: np.ndarray) -> FloatArray:
    """gwy_data_field_subtract_row_shifts(): field -= shifts per row."""
    return field - shifts[:, None]


def _choleski_decompose(dim: int, a: list[float]) -> bool:
    """gwy_math_choleski_decompose() packed lower-triangular loop, matching
    the INSTALLED libgwyd*dion2 2.71 binary arithmetic.

    The installed shared library was compiled with reciprocal-multiply
    codegen: after computing the diagonal s = sqrt(s), the inverse inv =
    1.0/s is hoisted once per k and every nondiagonal element is stored as
    r * inv (not r / s).  The frozen source text says r/s, but the compiled
    campaign evidence (linked against the installed library) follows the
    reciprocal form; bitwise parity with the probe therefore requires it.
    """
    for k in range(dim):
        s = a[k * (k + 1) // 2 + k]
        for i in range(k):
            s -= a[k * (k + 1) // 2 + i] * a[k * (k + 1) // 2 + i]
        if s <= 0.0:
            return False
        a[k * (k + 1) // 2 + k] = s = math.sqrt(s)
        inv = 1.0 / s
        for j in range(k + 1, dim):
            r = a[j * (j + 1) // 2 + k]
            for i in range(k):
                r -= a[k * (k + 1) // 2 + i] * a[j * (j + 1) // 2 + i]
            a[j * (j + 1) // 2 + k] = r * inv
    return True


def _choleski_solve(dim: int, a: Sequence[float], b: list[float]) -> None:
    """gwy_math_choleski_solve() exact forward/backward loop order."""
    for j in range(dim):
        for i in range(j):
            b[j] -= a[j * (j + 1) // 2 + i] * b[i]
        b[j] /= a[j * (j + 1) // 2 + j]
    for j in range(dim - 1, -1, -1):
        for i in range(j + 1, dim):
            b[j] -= a[i * (i + 1) // 2 + j] * b[i]
        b[j] /= a[j * (j + 1) // 2 + j]


def _validated_field(value: object) -> np.ndarray:
    data = np.array(np.asarray(value, dtype=np.float64), dtype=np.float64,
                    order="C", copy=True)
    if data.ndim != 2 or 0 in data.shape:
        raise ValueError("field must be non-empty two-dimensional")
    if not np.all(np.isfinite(data)):
        raise ValueError("field must be finite")
    return data


def _validated_mask(value: object | None, shape: tuple[int, int],
                    mask_present: bool) -> np.ndarray | None:
    if not mask_present or value is None:
        return None
    mask = np.array(np.asarray(value, dtype=np.float64), dtype=np.float64,
                    order="C", copy=True)
    if mask.shape != shape:
        raise ValueError(f"mask shape {mask.shape} != field shape {shape}")
    if not np.all(np.isfinite(mask)):
        raise ValueError("mask must be finite")
    return mask


@dataclass(frozen=True)
class AlignRowsSourceReference:
    """Every source-observable of the valid Align Rows operation."""

    input_snapshot: FloatArray
    xres: int
    yres: int
    method: str
    degree: int
    masking: str
    masking_enum: int
    mask_present: bool
    corrected_field: FloatArray
    background_field: FloatArray          # input - corrected
    delta_field: FloatArray               # corrected - input
    shifts: FloatArray                    # (yres,) final emitted profile
    row_valid_indices: tuple[tuple[int, ...], ...]
    row_valid_counts: tuple[int, ...]
    row_status: tuple[str, ...]           # corrected / unchanged
    # polynomial internal state (degree >= 1): per-row fitted coefficients
    poly_coefficients: FloatArray | None  # (yres, degree+1)
    # modus internal state
    modus_total_median: float | None
    modus_row_estimates: tuple[float, ...] | None
    # match internal state
    match_pair_lambdas: tuple[float, ...] | None   # per-pair pre-cumulative
    match_pair_wsum0: tuple[float, ...] | None     # diffnorm sums
    input_mutation_evidence: bool
    mask_mutation_evidence: bool


def _row_valid_indices(mask: FloatArray | None, masking: str,
                       xres: int, yres: int) -> tuple[tuple[int, ...], ...]:
    out: list[tuple[int, ...]] = []
    for i in range(yres):
        row = list(range(xres))
        if mask is not None and masking == "include":
            row = [j for j in row if float(mask[i, j]) > 0.0]
        elif mask is not None and masking == "exclude":
            row = [j for j in row if float(mask[i, j]) < 1.0]
        out.append(tuple(row))
    return tuple(out)


def oracle_align_rows_source(
    field: object,
    *,
    method: str,
    degree: int = 0,
    mask: object | None = None,
    masking: str = "ignore",
) -> AlignRowsSourceReference:
    """Run the exact source-semantic Align Rows oracle."""
    if method not in ("polynomial", "modus", "match"):
        raise ValueError(f"unknown method {method!r}")
    if masking not in _MASKING_ENUMS:
        raise ValueError(f"unknown masking mode {masking!r}")
    data = _validated_field(field)
    yres, xres = data.shape
    mask_present = mask is not None
    mask_arr = _validated_mask(mask, (yres, xres), mask_present)
    if mask_arr is not None and masking == "ignore":
        mask_arr = None  # _gwy_data_field_check_mask nulls it for IGNORE
        mask_present = False
    if method == "match" and xres < 2:
        raise ValueError("xres < 2 rejected: frozen source reads w[0]/"
                         "w[xres-2] unconditionally (out of bounds); no "
                         "retained campaign case exercises xres == 1")
    if degree < 0:
        raise ValueError("degree must be >= 0")

    row_valid = _row_valid_indices(mask_arr, masking, xres, yres)
    row_valid_counts = tuple(len(r) for r in row_valid)
    shifts: np.ndarray
    poly_coeffs: FloatArray | None = None

    if method == "polynomial" and degree == 0:
        # find_row_shifts_trimmed_mean(trimfrac=0, mincount auto)
        mincount = _gwy_round(math.log(xres) + 1.0)
        total_median = _median_mask(data, mask_arr, masking, xres, yres)
        sdata = np.empty(yres, dtype=np.float64)
        for i in range(yres):
            row_vals = _collected(data[i], mask_arr[i] if mask_arr is not None
                                  else None, masking, xres)
            if len(row_vals) >= mincount:
                if len(row_vals) == 1:
                    sdata[i] = row_vals[0]   # trimmed_mean_or_median n == 1
                else:
                    sdata[i] = _seq_sum(row_vals) / len(row_vals)
            else:
                sdata[i] = total_median
        shifts = _zero_level(sdata)

    elif method == "polynomial":
        # row_level_poly: full-field avg anchoring (unmasked)
        avg = _seq_sum([float(v) for v in data.ravel()]) / float(xres * yres)
        xc = 0.5 * (xres - 1)
        d = np.array(data, dtype=np.float64, copy=True)
        coeffs = np.zeros((yres, degree + 1), dtype=np.float64)
        shifts = np.empty(yres, dtype=np.float64)
        for i in range(yres):
            xp = [0.0] * (2 * degree + 1)
            zx = [0.0] * (degree + 1)
            for j in range(xres):
                if mask_arr is not None and masking == "include" \
                        and float(mask_arr[i, j]) <= 0.0:
                    continue
                if mask_arr is not None and masking == "exclude" \
                        and float(mask_arr[i, j]) >= 1.0:
                    continue
                p = 1.0
                x = j - xc
                for k in range(0, degree + 1):
                    xp[k] += p
                    zx[k] += p * float(d[i, j])
                    p *= x
                for k in range(degree + 1, 2 * degree + 1):
                    xp[k] += p
                    p *= x
            if xp[0] > degree:
                mat = [0.0] * ((degree + 1) * (degree + 2) // 2)
                for j in range(0, degree + 1):
                    for k in range(0, j + 1):
                        mat[j * (j + 1) // 2 + k] = xp[j + k]
                _choleski_decompose(degree + 1, mat)
                _choleski_solve(degree + 1, mat, zx)
            else:
                zx = [0.0] * (degree + 1)
            zx[0] -= avg
            shifts[i] = zx[0]
            coeffs[i] = zx
            for j in range(xres):
                p = 1.0
                x = j - xc
                z = 0.0
                for k in range(0, degree + 1):
                    z += p * zx[k]
                    p *= x
                d[i, j] -= z
        corrected = d
        poly_coeffs = coeffs

    elif method == "modus":
        total_median = _median_mask(data, mask_arr, masking, xres, yres)
        estimates: list[float] = []
        for i in range(yres):
            row_vals = _collected(data[i], mask_arr[i] if mask_arr is not None
                                  else None, masking, xres)
            cnt = len(row_vals)
            if cnt == 0:
                estimates.append(total_median)
            elif cnt < 9:
                estimates.append(_median_value(row_vals))
            else:
                seglen = _gwy_round(math.sqrt(cnt))
                srt = sorted(row_vals)
                bestj = 0
                bestdiff = math.inf
                for j in range(0, cnt - seglen + 1):
                    diff = srt[j + seglen - 1] - srt[j]
                    if diff < bestdiff:
                        bestdiff = diff
                        bestj = j
                modus = 0.0
                n = 0
                for j in range(seglen // 3, seglen - seglen // 3):
                    modus += srt[bestj + j]
                    n += 1
                estimates.append(modus / n)
        est_arr = np.array(estimates, dtype=np.float64)
        shifts = _zero_level(est_arr)

    else:  # match
        w = [0.0] * (xres - 1)
        s = [0.0] * yres
        pair_lambdas: list[float] = []
        pair_wsum0: list[float] = []

        def masked(j: int) -> bool:
            # Source skip predicate; NULL mask (IGNORE) never skips and the
            # C condition short-circuits before any NULL dereference.
            if masking == "include":
                if ma is None or mb is None:
                    return False
                return float(ma[j]) <= 0.0 or float(mb[j]) <= 0.0
            if masking == "exclude":
                if ma is None or mb is None:
                    return False
                return float(ma[j]) >= 1.0 or float(mb[j]) >= 1.0
            return False

        for i in range(1, yres):
            a = data[i - 1]
            b = data[i]
            ma = mask_arr[i - 1] if mask_arr is not None else None
            mb = mask_arr[i] if mask_arr is not None else None

            # diffnorm
            wsum = 0.0
            for j in range(xres - 1):
                if masked(j):
                    continue
                x = (float(a[j + 1]) - float(a[j]) - float(b[j + 1])
                     + float(b[j]))
                wsum += abs(x)
            if wsum == 0.0:
                s[i] = 0.0
                pair_wsum0.append(0.0)
                pair_lambdas.append(0.0)
                continue
            q = wsum / (xres - 1)
            # weights; wsum REASSIGNED to the effective weight sum
            wsum = 0.0
            for j in range(xres - 1):
                if masked(j):
                    w[j] = 0.0
                    continue
                x = (float(a[j + 1]) - float(a[j]) - float(b[j + 1])
                     + float(b[j]))
                w[j] = math.exp(-(x * x / (2.0 * q)))
                wsum += w[j]
            lam = (float(a[0]) - float(b[0])) * w[0]
            for j in range(1, xres - 1):
                if masked(j):
                    continue
                lam += (float(a[j]) - float(b[j])) * (w[j - 1] + w[j])
            lam += (float(a[xres - 1]) - float(b[xres - 1])) * w[xres - 2]
            lam /= 2.0 * wsum
            s[i] = -lam
            pair_wsum0.append(wsum)
            pair_lambdas.append(-lam)
        # cumulative
        s_arr = np.array(s, dtype=np.float64)
        cum = np.empty(yres, dtype=np.float64)
        cum[0] = s_arr[0]
        for k in range(1, yres):
            cum[k] = cum[k - 1] + s_arr[k]
        shifts = _zero_level(cum)
        pair_lambdas_t = tuple(pair_lambdas)
        pair_wsum0_t = tuple(pair_wsum0)

    corrected = d if method == "polynomial" and degree >= 1 \
        else _subtract_row_shifts(data, shifts)

    bg = data - corrected
    delta = corrected - data

    # row status: bitwise row comparison input vs corrected
    status: list[str] = []
    ib = np.ascontiguousarray(data).view(np.uint64)
    cb = np.ascontiguousarray(corrected).view(np.uint64)
    for i in range(yres):
        status.append("corrected" if not np.array_equal(ib[i], cb[i])
                      else "unchanged")

    return AlignRowsSourceReference(
        input_snapshot=data,
        xres=xres,
        yres=yres,
        method=method,
        degree=degree,
        masking=masking,
        masking_enum=_MASKING_ENUMS[masking],
        mask_present=mask_present,
        corrected_field=corrected,
        background_field=bg,
        delta_field=delta,
        shifts=shifts,
        row_valid_indices=row_valid,
        row_valid_counts=row_valid_counts,
        row_status=tuple(status),
        poly_coefficients=poly_coeffs,
        modus_total_median=(total_median if method == "modus" else None),
        modus_row_estimates=(tuple(estimates) if method == "modus" else None),
        match_pair_lambdas=(pair_lambdas_t if method == "match" else None),
        match_pair_wsum0=(pair_wsum0_t if method == "match" else None),
        input_mutation_evidence=True,
        mask_mutation_evidence=True,
    )
