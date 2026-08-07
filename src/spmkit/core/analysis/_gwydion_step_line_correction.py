"""Production kernel for Gwydion 2.71 Step Line Correction.

Independent implementation from the frozen source contract
(modules/process/linecorrect.c lines 78-192 with
libprocess/correct.c 1599-1671 and libprocess/filters.c 1158-1221).

Reproduces the exact source operation ordering with scalar float64
arithmetic: no NumPy reductions that could reassociate, no vectorized
threshold decisions, mutable scratch-row run scanning, exact division
order, IEEE division semantics for degenerate dimensions.

This module must not import fixtures, oracles, generators, tests or
Gwydion.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray


def _validated_field(value: object) -> FloatArray:
    source = np.asarray(value)
    if source.ndim != 2:
        raise ValueError("Step Line Correction data must be two-dimensional")
    if 0 in source.shape:
        raise ValueError("Step Line Correction data must have non-empty dimensions")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError("Step Line Correction data must contain real numeric values")
    values = np.array(source, dtype=np.float64, order="C", copy=True)
    if not np.isfinite(values).all():
        raise ValueError("Step Line Correction data must be finite")
    return values


def _sequential_sum(values: FloatArray) -> float:
    """gwy_data_field_get_sum: sequential accumulation in memory order."""
    total = 0.0
    for value in values.ravel():
        total += float(value)
    return total


def _row_upper_median(row: FloatArray) -> float:
    """gwy_math_median(n, array) = kth_rank(n, n/2): index n//2 order
    statistic of the sorted row (upper median for even widths)."""
    ordered = sorted(float(v) for v in row)
    return ordered[len(ordered) // 2]


def _ieee_divide(numerator: float, denominator: int) -> float:
    """IEEE-754 division with C semantics (0/0 -> NaN, x/0 -> +-Inf)."""
    with np.errstate(all="ignore"):
        return float(np.float64(numerator) / np.float64(denominator))


def _align_rows(field: FloatArray, medians: FloatArray,
                statistic_mean: float) -> FloatArray:
    """gwy_data_field_subtract_row_shifts (correct.c:1527-1551)."""
    aligned = field.copy()
    yres, xres = field.shape
    for i in range(yres):
        shift = float(medians[i]) - statistic_mean
        for j in range(xres):
            aligned[i, j] = aligned[i, j] - shift
    return aligned


def _repair_segment(work: FloatArray, top_index: int, scratch_row: list[float],
                    start: int, length: int, xres: int) -> None:
    """calculate_segment_correction (linecorrect.c:78-100).

    drow points at the triplet TOP row; drow[xres+j] and drow[2*xres+j]
    are the middle and bottom rows.  scratch_row is the mutable middle-row
    scratch buffer.  Accepted runs (length >= 4) write blended corrections;
    shorter runs are zeroed.
    """
    top = work[top_index]
    middle = work[top_index + 1]
    bottom = work[top_index + 2]
    if length >= 4:
        segment_residual = 0.0
        for k in range(length):
            column = start + k
            segment_residual += ((top[column] + bottom[column]) / 2.0
                                 - middle[column])
        segment_residual /= length
        for k in range(length):
            column = start + k
            local_residual = ((top[column] + bottom[column]) / 2.0
                              - middle[column])
            scratch_row[column] = (3.0 * segment_residual
                                   + local_residual) / 4.0
    else:
        for k in range(length):
            scratch_row[start + k] = 0.0


def _detector_pass(work: FloatArray, scratch: FloatArray) -> None:
    """line_correct_step_iter (linecorrect.c:102-157), in place.

    w accumulates the mean squared row-to-row difference with
    w = (w/(yres-1))/xres division order; every middle row is marked by
    strict v > 3.0*w; runs of exactly equal marks are scanned on the
    mutable scratch row; finally scratch is added to the field
    (gwy_data_field_sum_fields, arithmetic.c:50-74).
    """
    yres, xres = work.shape
    threshold = 3.0

    w = 0.0
    for i in range(yres - 1):
        upper = work[i]
        lower = work[i + 1]
        for j in range(xres):
            difference = lower[j] - upper[j]
            w += difference * difference
    w = _ieee_divide(_ieee_divide(w, yres - 1), xres)

    scratch.fill(0.0)

    for i in range(yres - 2):
        top = work[i]
        middle = work[i + 1]
        bottom = work[i + 2]
        marks = scratch[i + 1]
        for j in range(xres):
            centre = middle[j]
            product = (centre - top[j]) * (centre - bottom[j])
            if product > threshold * w:
                if 2.0 * centre - top[j] - bottom[j] > 0.0:
                    marks[j] = 1.0
                else:
                    marks[j] = -1.0

        # mutable run scan: equality on the current scratch values, which
        # earlier corrections may have replaced with blend floats
        run_length = 1
        for j in range(1, xres):
            if marks[j] == marks[j - 1]:
                run_length += 1
            else:
                if marks[j - 1]:
                    _repair_segment(work, i, marks, j - run_length,
                                    run_length, xres)
                run_length = 1
        if marks[xres - 1]:
            _repair_segment(work, i, marks, xres - run_length,
                            run_length, xres)

    for index in range(yres * xres):
        work.flat[index] = work.flat[index] + scratch.flat[index]


def _conservative_denoise_5(field: FloatArray) -> None:
    """gwy_data_field_filter_conservative(field, 5) (filters.c:1158-1221).

    Numerical no-op when xres < 5 or yres < 5 (filters.c:1174-1177); no
    GLib-style warning is emitted from the Python API.  Otherwise each
    pixel is clamped to the min/max of its clipped 5x5 neighbourhood with
    the centre excluded.
    """
    yres, xres = field.shape
    if xres < 5 or yres < 5:
        return
    source = field.copy()
    for r in range(yres):
        row_from = max(0, r - 2)
        row_to = min(yres - 1, r + 2)
        for c in range(xres):
            col_from = max(0, c - 2)
            col_to = min(xres - 1, c + 2)
            minimum = float("inf")
            maximum = float("-inf")
            for ii in range(row_to - row_from + 1):
                for jj in range(col_to - col_from + 1):
                    if r == ii + row_from and c == jj + col_from:
                        continue
                    neighbour = source[row_from + ii, col_from + jj]
                    if neighbour < minimum:
                        minimum = neighbour
                    if neighbour > maximum:
                        maximum = neighbour
            centre = source[r, c]
            if centre < minimum:
                field[r, c] = minimum
            elif centre > maximum:
                field[r, c] = maximum
            else:
                field[r, c] = centre


@dataclass(frozen=True)
class _StepLineCorrectionTrace:
    """All intermediate observables of the source operation (trace path).

    The trace uses the same numerical engine as the public path.
    """

    input_snapshot: FloatArray
    original_global_mean: float
    row_statistics: FloatArray
    zero_leveled_shifts: FloatArray
    field_after_row_alignment: FloatArray
    scratch_pass1: FloatArray
    field_after_pass1: FloatArray
    scratch_pass2: FloatArray
    field_after_pass2: FloatArray
    field_after_conservative_filter: FloatArray
    mean_restoration_offset: float
    final_corrected: FloatArray
    final_minus_input: FloatArray
    input_minus_final: FloatArray


def _gwydion_step_line_correction_result(
    data: object,
    *,
    trace: bool = False,
) -> FloatArray | _StepLineCorrectionTrace:
    """Run the Step Line Correction engine.

    With ``trace=False`` (the public path) returns the corrected field
    only.  With ``trace=True`` returns the complete private observable
    set; both paths execute the identical numerical engine.
    """
    field = _validated_field(data)
    yres, xres = field.shape
    n = yres * xres
    input_snapshot = field.copy()

    # linecorrect.c:177 — original global mean
    original_mean = _sequential_sum(field) / n

    # linecorrect.c:178 — row statistics and zero-levelled shifts
    statistics = np.array([_row_upper_median(field[i]) for i in range(yres)],
                          dtype=np.float64, order="C")
    statistic_total = 0.0
    for value in statistics:
        statistic_total += float(value)
    statistic_mean = statistic_total / yres
    shifts = statistics - statistic_mean
    aligned = _align_rows(field, statistics, statistic_mean)

    # linecorrect.c:182-186 — exactly two detector passes
    scratch = np.zeros((yres, xres), dtype=np.float64, order="C")
    _detector_pass(aligned, scratch)
    scratch_pass1 = scratch.copy()
    field_after_pass1 = aligned.copy()
    _detector_pass(aligned, scratch)
    scratch_pass2 = scratch.copy()
    field_after_pass2 = aligned.copy()

    # linecorrect.c:188 — size-5 conservative filter
    _conservative_denoise_5(aligned)
    field_after_filter = aligned.copy()

    # linecorrect.c:189 — mean-restoration offset, then add
    offset = original_mean - (_sequential_sum(aligned) / n)
    for index in range(n):
        aligned.flat[index] = aligned.flat[index] + offset
    final_corrected = aligned.copy()

    if not trace:
        return final_corrected

    return _StepLineCorrectionTrace(
        input_snapshot=input_snapshot,
        original_global_mean=original_mean,
        row_statistics=statistics,
        zero_leveled_shifts=shifts,
        field_after_row_alignment=_align_rows(field, statistics,
                                              statistic_mean),
        scratch_pass1=scratch_pass1,
        field_after_pass1=field_after_pass1,
        scratch_pass2=scratch_pass2,
        field_after_pass2=field_after_pass2,
        field_after_conservative_filter=field_after_filter,
        mean_restoration_offset=offset,
        final_corrected=final_corrected,
        final_minus_input=final_corrected - input_snapshot,
        input_minus_final=input_snapshot - final_corrected,
    )
