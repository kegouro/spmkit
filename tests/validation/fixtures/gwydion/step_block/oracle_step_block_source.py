"""Exact source-semantic Python oracle for Gwydion 2.71 Step Block Correction.

Reproduces the valid frozen-source numerical contract of
modules/process/blockstep.c (source-included kernel) for finite
two-dimensional fields with xres >= 2, using only the standard library and
NumPy.

Independence: no production imports, no fixture expected-output reads, no
Gwydion calls, no SciPy, no campaign-parser imports, no case identifiers.

Deliberate safe-contract divergences (documented, not silent):
  - xres < 2 is REJECTED: the frozen source performs an out-of-bounds read
    for xres=1 (blockstep.c construct_blocks/process_one_step_segment reads
    one row before the field; see the frozen-source-defect record).  The
    oracle never reproduces undefined behaviour.
  - non-finite inputs are rejected (finite-input policy).

The kth-rank / trimmed-mean helpers (gwymath-rank.c) are ported exactly:
gwy_math_kth_rank (median-of-three quickselect partition),
kth_rank_simple (all branches), order_3, kth_ranks_fastpath/kth_ranks_small
(nk=2), and the trimmed-mean retained sequential summation.  All
comparisons are strict `>` (GWY_ORDER semantics), matching the C source.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray

LTR = 1
RTL = -1


# ---------------------------------------------------------------------------
# Exact kth-rank / trimmed-mean helper port (libgwydion/gwymath-rank.c)
# ---------------------------------------------------------------------------

def _order(arr: list[float], start: int, a: int, b: int) -> None:
    """GWY_ORDER(gdouble, x, y): swap iff x > y (strict)."""
    if arr[start + a] > arr[start + b]:
        arr[start + a], arr[start + b] = arr[start + b], arr[start + a]


def _order_3(arr: list[float], start: int) -> None:
    """order_3(): sort three values with strict comparisons."""
    _order(arr, start, 0, 1)
    if arr[start + 2] < arr[start + 1]:
        arr[start + 1], arr[start + 2] = arr[start + 2], arr[start + 1]
        _order(arr, start, 0, 1)


def _kth_rank_simple(arr: list[float], start: int, n: int, k: int) -> float:
    """kth_rank_simple() verbatim branch structure (strict >)."""
    if n == 1:
        return arr[start]
    if n == 2:
        _order(arr, start, 0, 1)
        return arr[start + k]
    if n == 3 and k == 1:
        _order_3(arr, start)
        return arr[start + 1]
    if k == 0:
        a = arr[start]
        for i in range(1, n):
            c = arr[start + i]
            if c < a:
                arr[start + i] = a
                arr[start] = a = c
        return a
    if k == n - 1:
        a = arr[start + n - 1]
        for i in range(0, n - 1):
            c = arr[start + i]
            if c > a:
                arr[start + i] = a
                arr[start + n - 1] = a = c
        return a
    if k == 1:
        _order(arr, start, 0, 1)
        a = arr[start]
        b = arr[start + 1]
        for i in range(2, n):
            c = arr[start + i]
            if c < b:
                if c < a:
                    arr[start + i] = b
                    arr[start + 1] = b = a
                    arr[start] = a = c
                else:
                    arr[start + i] = b
                    arr[start + 1] = b = c
        return b
    if k == n - 2:
        _order(arr, start, n - 2, n - 1)
        a = arr[start + n - 1]
        b = arr[start + n - 2]
        for i in range(0, n - 2):
            c = arr[start + i]
            if c > b:
                if c > a:
                    arr[start + i] = b
                    arr[start + n - 2] = b = a
                    arr[start + n - 1] = a = c
                else:
                    arr[start + i] = b
                    arr[start + n - 2] = b = c
        return b
    if k == 2:
        _order_3(arr, start)
        a = arr[start]
        b = arr[start + 1]
        c = arr[start + 2]
        for i in range(3, n):
            d = arr[start + i]
            if d < c:
                if d < b:
                    if d < a:
                        arr[start + i] = c
                        arr[start + 2] = c = b
                        arr[start + 1] = b = a
                        arr[start] = a = d
                    else:
                        arr[start + i] = c
                        arr[start + 2] = c = b
                        arr[start + 1] = b = d
                else:
                    arr[start + i] = c
                    arr[start + 2] = c = d
        return c
    if k == n - 3:
        _order_3(arr, start + n - 3)
        a = arr[start + n - 1]
        b = arr[start + n - 2]
        c = arr[start + n - 3]
        for i in range(0, n - 3):
            d = arr[start + i]
            if d > c:
                if d > b:
                    if d > a:
                        arr[start + i] = c
                        arr[start + n - 3] = c = b
                        arr[start + n - 2] = b = a
                        arr[start + n - 1] = a = d
                    else:
                        arr[start + i] = c
                        arr[start + n - 3] = c = b
                        arr[start + n - 2] = b = d
                else:
                    arr[start + i] = c
                    arr[start + n - 3] = c = d
        return c
    raise AssertionError("kth_rank_simple: unreachable branch (source has "
                         "g_assert_not_reached)")


def _kth_rank(arr: list[float], start: int, n: int, k: int) -> float:
    """gwy_math_kth_rank(): median-of-three quickselect partition.

    Operates in place on arr[start:start+n]; rank k in [0, n).
    """
    lo = 0
    hi = n - 1
    while True:
        if hi <= lo + 2 or k <= lo + 2 or k + 2 >= hi:
            return _kth_rank_simple(arr, start + lo, hi + 1 - lo, k - lo)
        middle = (lo + hi) // 2
        _order(arr, start, middle, hi)
        _order(arr, start, lo, hi)
        _order(arr, start, middle, lo)
        arr[start + middle], arr[start + lo + 1] = \
            arr[start + lo + 1], arr[start + middle]
        ll = lo + 1
        hh = hi
        m = arr[start + lo]
        while True:
            ll += 1
            while m > arr[start + ll]:
                ll += 1
            hh -= 1
            while arr[start + hh] > m:
                hh -= 1
            if hh < ll:
                break
            arr[start + ll], arr[start + hh] = arr[start + hh], arr[start + ll]
        arr[start + lo] = arr[start + hh]
        arr[start + hh] = m
        if hh <= k:
            lo = hh
        if hh >= k:
            hi = hh - 1


def _kth_ranks_small(arr: list[float], k0: int, k1: int) -> None:
    """kth_ranks_small(nk=2) with the d0/d1 branch; mutates arr in place."""
    n = len(arr)
    d0 = n // 2 - k0 if k0 <= n // 2 else k0 - n // 2
    d1 = n // 2 - k1 if k1 <= n // 2 else k1 - n // 2
    if d0 <= d1:
        _kth_rank(arr, 0, n, k0)
        k0 += 1
        _kth_rank(arr, k0, n - k0, k1 - k0)
    else:
        _kth_rank(arr, 0, n, k1)
        _kth_rank(arr, 0, k1, k0)


def _trimmed_mean_inplace(arr: list[float], nlowest: int, nhighest: int) -> float:
    """gwy_math_trimmed_mean() exact port; mutates arr (selection shuffle).

    The C source advances a pointer (array += nlowest) instead of deleting;
    the full array keeps the post-selection rearrangement and the retained
    block is positions [nlowest, nlowest+nred).  This port matches that: the
    full array is rearranged in place and the retained sum is taken from
    positions nlowest..nlowest+nred-1.
    """
    n = len(arr)
    if not nlowest:
        if not nhighest:
            nred = n
        else:
            nred = n - nhighest
            _kth_rank(arr, 0, n, nred)
    elif not nhighest:
        nred = n - nlowest
        _kth_rank(arr, 0, n, nlowest - 1)
    else:
        _kth_ranks_small(arr, nlowest - 1, n - nhighest)
        nred = n - (nlowest + nhighest)
    s = 0.0
    for i in range(nred):
        s += arr[nlowest + i]
    return s / nred


# ---------------------------------------------------------------------------
# Step Block pipeline (blockstep.c source-semantic port)
# ---------------------------------------------------------------------------

def _validated_field(value: object) -> np.ndarray:
    source = np.asarray(value, dtype=np.float64)
    if source.ndim != 2:
        raise ValueError("field must be two-dimensional")
    if 0 in source.shape:
        raise ValueError("field must be non-empty")
    if not np.all(np.isfinite(source)):
        raise ValueError("field must be finite")
    xres = int(source.shape[1])
    if xres < 2:
        raise ValueError("xres < 2 rejected: the frozen source performs an "
                         "out-of-bounds read for xres=1 (SOURCE_DEFECT); "
                         "future SPMKit production must reject xres < 2")
    return np.array(source, dtype=np.float64, order="C", copy=True)


@dataclass(frozen=True)
class StepBlockSourceReference:
    """Every source-observable of the valid Step Block operation."""

    input_snapshot: FloatArray
    xres: int
    yres: int
    dy: float
    threshold_param: float
    effective_threshold: float
    rms_stat: float
    discontinuity_mask: FloatArray
    row_totalsteps: tuple[int, ...]
    row_pos: tuple[int, ...]
    row_score: tuple[float, ...]
    raw_boundary_candidates: tuple[tuple[int, int, float], ...]
    retained_blocks: tuple[tuple[int, int, float], ...]  # (i, fromleft, shift)
    sentinel: tuple[int, int, float]
    per_block_shifts_raw: tuple[FloatArray, ...]
    per_block_shifts_selected: tuple[FloatArray, ...]
    trim_low: int
    trim_high: int
    retained_count: int
    per_block_retained_sum: tuple[float, ...]
    block_count: int
    corrected_field: FloatArray
    correction_field: FloatArray
    preview_mask_discontinuity: FloatArray
    preview_mask_blocks: FloatArray
    input_mutation_evidence: bool


def oracle_step_block_source(
    field: object,
    *,
    threshold_param: float = 2.0,
    direction: str = "left_to_right",
    xreal: float | None = None,
    yreal: float | None = None,
) -> StepBlockSourceReference:
    """Run the source-semantic Step Block oracle.

    ``xreal``/``yreal`` are required for the exact threshold chain (the
    source derives dy = yreal/yres and uses it in the TAN_BETA0 res/real
    factor and the dy multiplication).
    """
    data = _validated_field(field)
    yres, xres = data.shape
    if not 0.1 <= threshold_param <= 10.0:
        raise ValueError("threshold_param must be within [0.1, 10.0]")
    if direction not in ("left_to_right", "right_to_left"):
        raise ValueError("direction must be left_to_right or right_to_left")
    scandir = LTR if direction == "left_to_right" else RTL

    # threshold chain (blockstep.c:556-561)
    dy = yreal / yres  # gwy_data_field_get_dy = yreal/yres
    col_tan = np.empty(xres, dtype=np.float64)
    for j in range(xres):
        if yres < 2:
            # source guard (linestats.c:627-628): to-from < 2 -> 0.0
            col_tan[j] = 0.0
            continue
        s = 0.0
        for i in range(1, yres):
            z = data[i, j] - data[i - 1, j]
            s += z * z
        col_tan[j] = math.sqrt(s / (yres - 1)) * (yres / (yres * dy))
    avg = 0.0
    for j in range(xres):
        avg += col_tan[j]
    avg /= xres
    rms = avg * dy
    effective = threshold_param * rms

    # mark_discontinuities (blockstep.c:283-384)
    imask = np.zeros((yres, xres), dtype=np.int64)
    totalsteps = [0] * yres
    for i in range(1, yres):
        c = 0
        for j in range(xres):
            flag = 1 if abs(data[i, j] - data[i - 1, j]) > effective else 0
            imask[i, j] = flag
            c += flag
        totalsteps[i] = c

    scores = [0.0] * yres
    positions = [0] * yres
    for i in range(1, yres):
        ntotal = totalsteps[i - 1] if scandir == LTR else totalsteps[i]
        best = -1
        bestpos = 0
        seenup = 0
        seendown = 0
        j = 0
        while True:
            if scandir == LTR:
                nleft = seendown
                nright = ntotal - seenup
            else:
                nleft = seenup
                nright = ntotal - seendown
            if nleft + nright > best:
                best = nleft + nright
                bestpos = j
            if j == xres:
                break
            seenup += int(imask[i - 1, j])
            seendown += int(imask[i, j])
            j += 1
        positions[i] = bestpos
        scores[i] = float(best)

    # discontinuity preview mask (blockstep.c:373-380)
    disc = np.zeros((yres, xres), dtype=np.float64)
    flat_imask = imask.ravel()
    for i in range(xres * yres - xres):
        disc.ravel()[i] = float(max(flat_imask[i], flat_imask[i + xres]))
    for i in range(xres * yres - xres, xres * yres):
        disc.ravel()[i] = float(flat_imask[i])

    # construct_blocks (blockstep.c:403-502)
    minlength = int(3 * xres / 4)
    candidates = []
    for i in range(1, yres):
        if scores[i] >= minlength:
            if scandir == LTR and positions[i] == xres:
                if i == yres - 1:
                    continue
                bs_i = i + 1
                fromleft = 0
            elif scandir == RTL and positions[i] == 0:
                if i == yres - 1:
                    continue
                bs_i = i + 1
                fromleft = xres
            else:
                bs_i = i
                fromleft = positions[i]
            candidates.append([bs_i, fromleft, scores[i]])

    # adjacent-boundary elimination (blockstep.c:447-457): a single
    # backward pass, exactly like the C for (k = len-1; k; k--) loop
    k = len(candidates) - 1
    while k > 0:
        bs0 = candidates[k - 1]
        bs1 = candidates[k]
        if bs1[0] - bs0[0] <= 1:
            if bs1[2] > bs0[2]:
                del candidates[k - 1]
            else:
                del candidates[k]
        k -= 1

    # shift estimation + trimmed mean (blockstep.c:463-484)
    blocks: list[tuple[int, int, float]] = []
    shifts_raw_all = []
    shifts_sel_all = []
    retained_sums = []
    flat = data.ravel()
    trim_low = xres // 4
    trim_high = xres // 4
    retained_count = xres - (trim_low + trim_high)
    for bs in candidates:
        cand_i: int = int(bs[0])
        cand_fromleft: int = int(bs[1])
        shifts = [0.0] * xres
        row_base = (cand_i - 1) * xres
        if scandir == LTR:
            _segment(flat, xres, row_base, shifts, 0, cand_fromleft)
            row_base -= xres
            _segment(flat, xres, row_base, shifts, cand_fromleft,
                     xres - cand_fromleft)
        else:
            _segment(flat, xres, row_base, shifts, cand_fromleft,
                     xres - cand_fromleft)
            row_base -= xres
            _segment(flat, xres, row_base, shifts, 0, cand_fromleft)
        raw = list(shifts)
        sel = list(shifts)
        tm = _trimmed_mean_inplace(sel, trim_low, trim_high)
        retained = sel[trim_low:trim_low + retained_count]
        ssum = 0.0
        for v in retained:
            ssum += v
        # the source's post-selection array keeps its full length
        sel = sel[:xres]
        shifts_raw_all.append(np.array(raw, dtype=np.float64))
        shifts_sel_all.append(np.array(sel, dtype=np.float64))
        retained_sums.append(ssum)
        blocks.append((cand_i - 1, cand_fromleft, tm))  # bs->i-- (line 481)

    sentinel = (yres + 1, xres, 0.0)

    # apply_correction (blockstep.c:504-540); the sentinel terminates the
    # walk exactly as the C source's appended sentinel block does
    corrected = np.array(data, dtype=np.float64, order="C", copy=True)
    shift = 0.0
    b = 0
    walk = list(blocks) + [sentinel]
    for i in range(blocks[0][0], yres) if blocks else ():
        row = corrected[i]
        if i == walk[b][0]:
            bi, fl, sh = walk[b]
            if scandir == LTR:
                for j in range(fl):
                    row[j] += shift
                shift -= sh
                for j in range(fl, xres):
                    row[j] += shift
            else:
                for j in range(fl, xres):
                    row[j] += shift
                shift -= sh
                for j in range(fl):
                    row[j] += shift
            b += 1
        else:
            row += shift

    correction = corrected - data

    # blocks preview mask (process_one_step_segment mrow writes, line 396-399)
    bmask = np.zeros((yres, xres), dtype=np.float64)
    for cand, block in zip(candidates, blocks, strict=True):
        bs_i_pre = block[0] + 1
        mask_fromleft = int(cand[1])
        mrow_base = (bs_i_pre - 1) * xres
        # the source decrements only the data row pointer, not mrow: both
        # process_one_step_segment calls write the SAME mask row pair
        if scandir == LTR:
            _mask_segment(bmask, mrow_base, 0, mask_fromleft, xres)
            _mask_segment(bmask, mrow_base, mask_fromleft,
                          xres - mask_fromleft, xres)
        else:
            _mask_segment(bmask, mrow_base, mask_fromleft,
                          xres - mask_fromleft, xres)
            _mask_segment(bmask, mrow_base, 0, mask_fromleft, xres)

    return StepBlockSourceReference(
        input_snapshot=data,
        xres=xres,
        yres=yres,
        dy=dy,
        threshold_param=threshold_param,
        effective_threshold=effective,
        rms_stat=rms,
        discontinuity_mask=disc,
        row_totalsteps=tuple(totalsteps),
        row_pos=tuple(positions),
        row_score=tuple(scores),
        raw_boundary_candidates=tuple((int(c[0]), int(c[1]), float(c[2]))
                                      for c in candidates),
        retained_blocks=tuple(blocks),
        sentinel=sentinel,
        per_block_shifts_raw=tuple(shifts_raw_all),
        per_block_shifts_selected=tuple(shifts_sel_all),
        trim_low=trim_low,
        trim_high=trim_high,
        retained_count=retained_count,
        per_block_retained_sum=tuple(retained_sums),
        block_count=len(blocks),
        corrected_field=corrected,
        correction_field=correction,
        preview_mask_discontinuity=disc,
        preview_mask_blocks=bmask,
        input_mutation_evidence=False,
    )


def _segment(flat: np.ndarray, xres: int, row_base: int, shifts: list[float],
             from_: int, length: int) -> None:
    for j in range(length):
        shifts[from_ + j] = flat[row_base + xres + from_ + j] - \
            flat[row_base + from_ + j]


def _mask_segment(bmask: np.ndarray, mrow_base: int, from_: int,
                  length: int, xres: int) -> None:
    for j in range(length):
        bmask.ravel()[mrow_base + xres + from_ + j] = 1.0
        bmask.ravel()[mrow_base + from_ + j] = 1.0
