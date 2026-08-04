"""Independent Python reference for Gwydion 2.71 Mark Inverted Rows.

Reproduces the numerical operation of modules/process/linecorrect.c
(mark_inverted_lines, lines 209-331; row_correlation, 194-207) with the
exact source operation ordering, using only the Python standard library
and NumPy.

Independence: this module does not import any SPMKit production module,
any private Gwydion-compatibility kernel, the compiled-campaign parser,
or any fixture file.  It does not call Gwydion.

All inputs are finite float64 arrays; NaN and infinities are rejected.
The data field is never modified.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray


def _validated_field(value: object) -> np.ndarray:
    source = np.asarray(value, dtype=np.float64)
    if source.ndim != 2:
        raise ValueError("Mark Inverted Rows data must be two-dimensional")
    if 0 in source.shape:
        raise ValueError("Mark Inverted Rows data must have non-empty dimensions")
    if not np.isfinite(source).all():
        raise ValueError("Mark Inverted Rows data must be finite")
    return np.array(source, dtype=np.float64, order="C", copy=True)


def _validated_mask(value: object, shape: tuple[int, int]) -> np.ndarray:
    mask = _validated_field(value)
    if mask.shape != shape:
        raise ValueError("Mark Inverted Rows mask shape must match data")
    return mask


def _row_mean(row: np.ndarray) -> float:
    """gwy_data_line_get_avg (linestats.c:206-217): sequential sum / res."""
    total = 0.0
    for v in row:
        total += v
    return total / row.shape[0]


def _row_rms(row: np.ndarray, mean: float) -> float:
    """gwy_data_line_get_rms (linestats.c:228-240)."""
    total = 0.0
    for v in row:
        d = v - mean
        total += d * d
    return float(np.sqrt(total / row.shape[0]))


def _row_correlation(row_a: np.ndarray, mean_a: float, rms_a: float,
                     row_b: np.ndarray, mean_b: float, rms_b: float,
                     total_rms: float) -> float:
    """row_correlation (linecorrect.c:194-207): un-normalised covariance
    divided by (rms_a*rms_b + total_rms**2).  The numerator is NOT divided
    by the sample count."""
    s = 0.0
    for va, vb in zip(row_a, row_b, strict=True):
        s += (va - mean_a) * (vb - mean_b)
    return s / (rms_a * rms_b + total_rms * total_rms)


@dataclass(frozen=True)
class MarkInvertedRowsReference:
    """Every observable of the source operation."""

    input_snapshot: FloatArray
    global_mean: float
    global_rms: float
    guard_triggered: bool
    row_means: FloatArray | None
    row_rms: FloatArray | None
    raw_weights: FloatArray | None
    has_negative_weight: bool | None
    block_summed_weights: FloatArray | None
    anchor_index: int | None
    anchor_weight: float | None
    generated_mask: FloatArray | None
    mask_max: float | None
    would_create_mask: bool | None
    would_overwrite_existing_mask: bool | None
    existing_mask_before: FloatArray | None
    existing_mask_after: FloatArray | None
    input_after: FloatArray
    early_return_no_negative: bool


def oracle_mark_inverted_rows(data: object,
                              existing_mask: object | None = None
                              ) -> MarkInvertedRowsReference:
    """Reproduce Gwydion 2.71 mark_inverted_lines in exact source order.

    ``existing_mask`` models the channel's pre-existing mask field
    (linecorrect.c:224-228); the operation overwrites it in place after
    actual inversion detection (321-324) and leaves it untouched on the
    no-negative early return (255-260).  A future SPMKit public adaptation
    may choose different mask state handling; this oracle models the source.
    """
    field = _validated_field(data)
    yres, xres = field.shape
    n = yres * xres
    input_snapshot = field.copy()
    mask = None if existing_mask is None else _validated_mask(existing_mask,
                                                              (yres, xres))
    existing_before = None if mask is None else mask.copy()

    # global mean and RMS (stats.c:567-569, 680-705)
    total = 0.0
    for v in field.flat:
        total += v
    global_mean = total / n
    sum2 = 0.0
    for v in field.flat:
        d = v - global_mean
        sum2 += d * d
    global_rms = float(np.sqrt(sum2 / n))

    # linecorrect.c:234-235 — dimension and total-RMS guards
    guard = global_rms <= 0.0 or yres < 3 or xres < 3
    if guard:
        return MarkInvertedRowsReference(
            input_snapshot=input_snapshot,
            global_mean=global_mean,
            global_rms=global_rms,
            guard_triggered=True,
            row_means=None,
            row_rms=None,
            raw_weights=None,
            has_negative_weight=None,
            block_summed_weights=None,
            anchor_index=None,
            anchor_weight=None,
            generated_mask=None,
            mask_max=None,
            would_create_mask=None,
            would_overwrite_existing_mask=None,
            existing_mask_before=existing_before,
            existing_mask_after=None if mask is None else mask.copy(),
            input_after=field.copy(),
            early_return_no_negative=False,
        )

    # linecorrect.c:237-243 — per-row means and RMS values
    row_means = np.array([_row_mean(field[i]) for i in range(yres)],
                         dtype=np.float64)
    row_rms = np.array([_row_rms(field[i], float(row_means[i]))
                        for i in range(yres)], dtype=np.float64)

    # linecorrect.c:246-254 — adjacent-row correlation weights
    weights = np.array([
        _row_correlation(field[i], float(row_means[i]), float(row_rms[i]),
                         field[i + 1], float(row_means[i + 1]),
                         float(row_rms[i + 1]), global_rms)
        for i in range(yres - 1)], dtype=np.float64)
    has_negative = bool(np.any(weights < 0.0))

    # linecorrect.c:255-260 — no-negative early return: no mask is created
    # and an existing mask is left untouched
    if not has_negative:
        return MarkInvertedRowsReference(
            input_snapshot=input_snapshot,
            global_mean=global_mean,
            global_rms=global_rms,
            guard_triggered=False,
            row_means=row_means,
            row_rms=row_rms,
            raw_weights=weights,
            has_negative_weight=False,
            block_summed_weights=None,
            anchor_index=None,
            anchor_weight=None,
            generated_mask=None,
            mask_max=None,
            would_create_mask=False,
            would_overwrite_existing_mask=False,
            existing_mask_before=existing_before,
            existing_mask_after=None if mask is None else mask.copy(),
            input_after=field.copy(),
            early_return_no_negative=True,
        )

    # linecorrect.c:262-278 — in-place same-sign block summation
    block = weights.copy()
    from_index = 0
    for i in range(yres - 2):
        if block[i] * block[i + 1] < 0.0:
            s = 0.0
            for j in range(from_index, i + 1):
                s += block[j]
            for j in range(from_index, i + 1):
                block[j] = s
            from_index = i + 1
    s = 0.0
    for j in range(from_index, yres - 1):
        s += block[j]
    for j in range(from_index, yres - 1):
        block[j] = s

    # linecorrect.c:280-287 — strict-first-maximum anchor selection
    wmax = 0.0
    anchor = 0
    for i in range(yres - 1):
        if block[i] > wmax:
            wmax = float(block[i])
            anchor = i

    # linecorrect.c:292-293 — mask field (all zero)
    generated = np.zeros((yres, xres), dtype=np.float64, order="C")

    # linecorrect.c:296-302 — downward sign-toggle propagation
    inverted = False
    for i in range(anchor, yres - 1):
        if weights[i] < 0.0:
            inverted = not inverted
        if inverted:
            generated[i + 1, :] = 1.0

    # linecorrect.c:305-311 — upward sign-toggle propagation
    inverted = False
    for i in range(anchor, -1, -1):
        if weights[i] < 0.0:
            inverted = not inverted
        if inverted:
            generated[i, :] = 1.0

    mask_max = float(generated.max())
    would_create = mask_max > 0.0

    # linecorrect.c:315-318 — early return only when no existing mask and
    # the generated mask is empty (unreachable when has_negative, per the
    # documented reachability argument, but modelled faithfully)
    if mask is None and mask_max <= 0.0:
        return MarkInvertedRowsReference(
            input_snapshot=input_snapshot,
            global_mean=global_mean,
            global_rms=global_rms,
            guard_triggered=False,
            row_means=row_means,
            row_rms=row_rms,
            raw_weights=weights,
            has_negative_weight=True,
            block_summed_weights=block,
            anchor_index=anchor,
            anchor_weight=wmax,
            generated_mask=generated,
            mask_max=mask_max,
            would_create_mask=False,
            would_overwrite_existing_mask=False,
            existing_mask_before=None,
            existing_mask_after=None,
            input_after=field.copy(),
            early_return_no_negative=False,
        )

    # linecorrect.c:321-327 — existing mask overwritten in place
    would_overwrite = mask is not None
    existing_after = None
    if mask is not None:
        mask[...] = generated
        existing_after = mask.copy()

    return MarkInvertedRowsReference(
        input_snapshot=input_snapshot,
        global_mean=global_mean,
        global_rms=global_rms,
        guard_triggered=False,
        row_means=row_means,
        row_rms=row_rms,
        raw_weights=weights,
        has_negative_weight=True,
        block_summed_weights=block,
        anchor_index=anchor,
        anchor_weight=wmax,
        generated_mask=generated,
        mask_max=mask_max,
        would_create_mask=would_create,
        would_overwrite_existing_mask=would_overwrite,
        existing_mask_before=existing_before,
        existing_mask_after=existing_after,
        input_after=field.copy(),
        early_return_no_negative=False,
    )
