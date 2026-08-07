"""Independent Python reference for Gwydion 2.71 Step Line Correction.

Reproduces the numerical operation of modules/process/linecorrect.c
(line_correct_step, lines 159-192; line_correct_step_iter, 102-157;
calculate_segment_correction, 78-100) with the exact source operation
ordering, using only the Python standard library and NumPy.

Independence: this module does not import any SPMKit production module,
any private Gwyddion-compatibility kernel, the compiled-campaign parser,
or any fixture file.  It does not call Gwydion.

All inputs are finite float64 arrays; NaN and infinities are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray


def _validated_field(value: object) -> np.ndarray:
    source = np.asarray(value, dtype=np.float64)
    if source.ndim != 2:
        raise ValueError("Step Line Correction data must be two-dimensional")
    if 0 in source.shape:
        raise ValueError("Step Line Correction data must have non-empty dimensions")
    if not np.isfinite(source).all():
        raise ValueError("Step Line Correction data must be finite")
    return np.array(source, dtype=np.float64, order="C", copy=True)


def _upper_median(row: np.ndarray) -> float:
    """gwy_math_median(n, array) = kth_rank(n, n/2): the n//2-th order
    statistic (upper median for even n)."""
    ordered = sorted(float(v) for v in row)
    return ordered[len(ordered) // 2]


def _mean_in_order(values: list[float]) -> float:
    total = 0.0
    for v in values:
        total += v
    return total / len(values)


def _segment_correction(work: np.ndarray, top_index: int, mrow: list[float],
                        start: int, length: int, xres: int) -> None:
    """calculate_segment_correction (linecorrect.c:78-100).

    drow points at the TOP row of the triplet; drow[xres+j] and
    drow[2*xres+j] are the middle and bottom rows via pointer arithmetic.
    mrow is the mutable scratch-row (middle row of the triplet).
    """
    top = work[top_index]
    mid = work[top_index + 1]
    bot = work[top_index + 2]
    if length >= 4:
        corr = 0.0
        for k in range(length):
            j = start + k
            corr += (top[j] + bot[j]) / 2.0 - mid[j]
        corr /= length
        for k in range(length):
            j = start + k
            mrow[j] = (3.0 * corr + (top[j] + bot[j]) / 2.0 - mid[j]) / 4.0
    else:
        for k in range(length):
            mrow[start + k] = 0.0


def _ieee_div(a: float, b: float) -> float:
    """IEEE-754 division with C semantics (0/0 -> NaN, x/0 -> +-Inf)."""
    with np.errstate(all="ignore"):
        return float(np.float64(a) / np.float64(b))


def _step_pass(work: np.ndarray, scratch: np.ndarray) -> None:
    """One line_correct_step_iter (linecorrect.c:102-157), in place."""
    yres, xres = work.shape
    threshold = 3.0

    # w: mean squared row-to-row difference (117-125), division order
    # w = (w/(yres-1))/xres ; for yres == 1 the C code yields 0.0/0 = NaN
    w = 0.0
    for i in range(yres - 1):
        drow = work[i]
        nrow = work[i + 1]
        for j in range(xres):
            v = nrow[j] - drow[j]
            w += v * v
    w = _ieee_div(_ieee_div(w, yres - 1), xres)

    scratch.fill(0.0)

    # triplet mark loop (127-140); middle row i+1
    for i in range(yres - 2):
        top = work[i]
        mid = work[i + 1]
        bot = work[i + 2]
        mrow = scratch[i + 1]
        for j in range(xres):
            u = mid[j]
            v = (u - top[j]) * (u - bot[j])
            if v > threshold * w:
                if 2.0 * u - top[j] - bot[j] > 0.0:
                    mrow[j] = 1.0
                else:
                    mrow[j] = -1.0

        # mutable run scan (142-153); corrected values replace the marks
        length = 1
        for j in range(1, xres):
            if mrow[j] == mrow[j - 1]:
                length += 1
            else:
                if mrow[j - 1]:
                    _segment_correction(work, i, mrow, j - length, length, xres)
                length = 1
        if mrow[xres - 1]:
            _segment_correction(work, i, mrow, xres - length, length, xres)

    # gwy_data_field_sum_fields (arithmetic.c:50): sequential field += scratch
    for idx in range(yres * xres):
        work.flat[idx] = work.flat[idx] + scratch.flat[idx]


def _conservative_filter(work: np.ndarray) -> None:
    """gwy_data_field_filter_conservative(work, 5) (filters.c:1158-1221).

    No-op with a warning when xres < 5 or yres < 5 (filters.c:1174-1177);
    per-pixel 5x5 clipped window, centre excluded, clamp to neighbour
    min/max.  The C implementation computes every output pixel from the
    input field, so direct per-pixel evaluation is order-equivalent.
    """
    yres, xres = work.shape
    if xres < 5 or yres < 5:
        return
    source = work.copy()
    for r in range(yres):
        ifrom = max(0, r - 2)
        ito = min(yres - 1, r + 2)
        for c in range(xres):
            jfrom = max(0, c - 2)
            jto = min(xres - 1, c + 2)
            minval = float("inf")
            maxval = float("-inf")
            for ii in range(ito - ifrom + 1):
                for jj in range(jto - jfrom + 1):
                    if r == ii + ifrom and c == jj + jfrom:
                        continue
                    value = source[ifrom + ii, jfrom + jj]
                    if value < minval:
                        minval = value
                    if value > maxval:
                        maxval = value
            centre = source[r, c]
            if centre < minval:
                work[r, c] = minval
            elif centre > maxval:
                work[r, c] = maxval
            else:
                work[r, c] = centre


@dataclass(frozen=True)
class StepLineCorrectionReference:
    """Every intermediate and final observable of the source operation."""

    input_snapshot: FloatArray
    original_global_mean: float
    raw_row_statistics: FloatArray
    zero_leveled_row_shifts: FloatArray
    field_after_initial_row_alignment: FloatArray
    correction_scratch_pass1: FloatArray
    field_after_pass1: FloatArray
    correction_scratch_pass2: FloatArray
    field_after_pass2: FloatArray
    field_after_conservative_filter: FloatArray
    final_mean_restoration_offset: float
    final_corrected_field: FloatArray
    final_minus_input: FloatArray
    input_minus_final: FloatArray


def oracle_step_line_correction(data: object) -> StepLineCorrectionReference:
    """Reproduce Gwydion 2.71 line_correct_step in exact source order."""
    field = _validated_field(data)
    yres, xres = field.shape
    n = yres * xres
    input_snapshot = field.copy()

    # linecorrect.c:177 — original global mean (sequential sum / n)
    original_global_mean = float(np.sum(field, dtype=np.float64) / n)

    # linecorrect.c:178 — row statistic (upper median) and zero-leveled
    # shifts (correct.c:1599-1671, 1565-1568)
    raw_statistics = np.array(
        [_upper_median(field[i]) for i in range(yres)], dtype=np.float64)
    statistic_mean = _mean_in_order([float(v) for v in raw_statistics])
    shifts = raw_statistics - statistic_mean
    aligned = field.copy()
    for i in range(yres):
        z = float(shifts[i])
        for j in range(xres):
            aligned[i, j] = aligned[i, j] - z

    # two passes (182-186)
    scratch = np.zeros((yres, xres), dtype=np.float64, order="C")
    _step_pass(aligned, scratch)
    scratch_pass1 = scratch.copy()
    field_after_pass1 = aligned.copy()
    _step_pass(aligned, scratch)
    scratch_pass2 = scratch.copy()
    field_after_pass2 = aligned.copy()

    # linecorrect.c:188 — conservative filter size 5
    _conservative_filter(aligned)
    field_after_filter = aligned.copy()

    # linecorrect.c:189 — mean restoration offset then add
    offset = original_global_mean - float(np.sum(aligned, dtype=np.float64) / n)
    for idx in range(n):
        aligned.flat[idx] = aligned.flat[idx] + offset
    final_corrected = aligned.copy()

    return StepLineCorrectionReference(
        input_snapshot=input_snapshot,
        original_global_mean=original_global_mean,
        raw_row_statistics=raw_statistics,
        zero_leveled_row_shifts=shifts,
        field_after_initial_row_alignment=_initial_alignment(field, shifts),
        correction_scratch_pass1=scratch_pass1,
        field_after_pass1=field_after_pass1,
        correction_scratch_pass2=scratch_pass2,
        field_after_pass2=field_after_pass2,
        field_after_conservative_filter=field_after_filter,
        final_mean_restoration_offset=offset,
        final_corrected_field=final_corrected,
        final_minus_input=final_corrected - input_snapshot,
        input_minus_final=input_snapshot - final_corrected,
    )


def _initial_alignment(field: np.ndarray, shifts: np.ndarray) -> np.ndarray:
    """field after gwy_data_field_subtract_row_shifts (correct.c:1527)."""
    aligned = field.copy()
    yres, xres = field.shape
    for i in range(yres):
        z = float(shifts[i])
        for j in range(xres):
            aligned[i, j] = aligned[i, j] - z
    return aligned
