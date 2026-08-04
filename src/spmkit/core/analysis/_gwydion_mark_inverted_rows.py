"""Production kernel for Gwydion 2.71 Mark Inverted Rows.

Independent implementation from the frozen source contract
(modules/process/linecorrect.c lines 194-331).

Reproduces the exact source operation ordering with scalar float64
arithmetic: sequential per-row means and RMS, the un-normalised covariance
numerator divided by (rms_a*rms_b + total_rms**2), in-place same-sign
block summation, strict-first-maximum anchor selection, and sign-toggle
propagation that flips only at strictly negative raw weights.  The data
field is never modified.

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
        raise ValueError("Mark Inverted Rows data must be two-dimensional")
    if 0 in source.shape:
        raise ValueError("Mark Inverted Rows data must have non-empty dimensions")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError("Mark Inverted Rows data must contain real numeric values")
    values = np.array(source, dtype=np.float64, order="C", copy=True)
    if not np.isfinite(values).all():
        raise ValueError("Mark Inverted Rows data must be finite")
    return values


def _validated_existing_mask(value: object,
                             shape: tuple[int, int]) -> FloatArray:
    """Validate a private existing mask WITHOUT copying it.

    The source operation overwrites the data-browser mask field in place
    (linecorrect.c:321-324); to model that faithfully, the caller's array
    is mutated directly when detection occurs.  The public SPMKit API
    passes None and never exposes this mutation path.
    """
    source = np.asarray(value)
    if source.ndim != 2:
        raise ValueError("Mark Inverted Rows existing mask must be two-dimensional")
    if source.shape != shape:
        raise ValueError("Mark Inverted Rows existing mask shape must match data")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError("Mark Inverted Rows existing mask must be real numeric")
    if not np.isfinite(source).all():
        raise ValueError("Mark Inverted Rows existing mask must be finite")
    return np.asarray(source, dtype=np.float64)


def _row_mean(row: FloatArray) -> float:
    """gwy_data_line_get_avg (linestats.c:206-217): sequential sum / res."""
    total = 0.0
    for value in row:
        total += float(value)
    return total / row.shape[0]


def _row_rms(row: FloatArray, mean: float) -> float:
    """gwy_data_line_get_rms (linestats.c:228-240)."""
    total = 0.0
    for value in row:
        deviation = float(value) - mean
        total += deviation * deviation
    return float(np.sqrt(total / row.shape[0]))


def _adjacent_weight(row_a: FloatArray, mean_a: float, rms_a: float,
                     row_b: FloatArray, mean_b: float, rms_b: float,
                     total_rms: float) -> float:
    """row_correlation (linecorrect.c:194-207).

    The numerator is the sequential sum of (x-mean_a)*(y-mean_b) and is
    NOT divided by the sample count; the denominator is
    rms_a*rms_b + total_rms**2.
    """
    numerator = 0.0
    for va, vb in zip(row_a, row_b, strict=True):
        numerator += (float(va) - mean_a) * (float(vb) - mean_b)
    return numerator / (rms_a * rms_b + total_rms * total_rms)


@dataclass(frozen=True)
class _GwydionMarkInvertedRowsResult:
    """Private immutable result preserving the full source semantics."""

    generated_mask: FloatArray | None      # None when no mask would be created
    global_mean: float
    global_rms: float
    guard_triggered: bool
    row_means: FloatArray | None
    row_rms: FloatArray | None
    raw_weights: FloatArray | None
    has_negative_weight: bool
    block_summed_weights: FloatArray | None
    anchor_index: int | None
    anchor_weight: float | None
    mask_max: float | None
    would_create_mask: bool
    would_overwrite_existing_mask: bool
    existing_mask_before: FloatArray | None
    existing_mask_after: FloatArray | None
    input_snapshot: FloatArray


def _gwydion_mark_inverted_rows_result(
    data: object,
    *,
    existing_mask: object | None = None,
) -> _GwydionMarkInvertedRowsResult:
    """Run the Mark Inverted Rows engine.

    ``existing_mask`` is a private-validation-only input modelling the
    Gwydion data-browser mask field: preserved untouched on the no-negative
    early return and overwritten bitwise by the generated binary mask after
    actual detection.  The public SPMKit API does not keep persistent mask
    state and passes None.
    """
    field = _validated_field(data)
    yres, xres = field.shape
    n = yres * xres
    input_snapshot = field.copy()
    existing = (None if existing_mask is None
                else _validated_existing_mask(existing_mask, (yres, xres)))
    existing_before = None if existing is None else existing.copy()

    # global mean and RMS (stats.c:567-569, 680-705)
    total = 0.0
    for value in field.ravel():
        total += float(value)
    global_mean = total / n
    sum_squares = 0.0
    for value in field.ravel():
        deviation = float(value) - global_mean
        sum_squares += deviation * deviation
    global_rms = float(np.sqrt(sum_squares / n))

    # linecorrect.c:234-235 — dimension and total-RMS guards
    if global_rms <= 0.0 or yres < 3 or xres < 3:
        return _GwydionMarkInvertedRowsResult(
            generated_mask=None,
            global_mean=global_mean,
            global_rms=global_rms,
            mask_max=None,
            guard_triggered=True,
            row_means=None,
            row_rms=None,
            raw_weights=None,
            has_negative_weight=False,
            block_summed_weights=None,
            anchor_index=None,
            anchor_weight=None,
            would_create_mask=False,
            would_overwrite_existing_mask=False,
            existing_mask_before=existing_before,
            existing_mask_after=None if existing is None else existing.copy(),
            input_snapshot=input_snapshot,
        )

    # linecorrect.c:237-243 — per-row means and RMS values
    means = np.array([_row_mean(field[i]) for i in range(yres)],
                     dtype=np.float64, order="C")
    rms = np.array([_row_rms(field[i], float(means[i])) for i in range(yres)],
                   dtype=np.float64, order="C")

    # linecorrect.c:246-254 — adjacent-row weights
    weights = np.array([
        _adjacent_weight(field[i], float(means[i]), float(rms[i]),
                         field[i + 1], float(means[i + 1]), float(rms[i + 1]),
                         global_rms)
        for i in range(yres - 1)], dtype=np.float64, order="C")
    has_negative = bool(np.any(weights < 0.0))

    # linecorrect.c:255-260 — no-negative early return: no mask created,
    # existing mask preserved
    if not has_negative:
        return _GwydionMarkInvertedRowsResult(
            generated_mask=None,
            global_mean=global_mean,
            global_rms=global_rms,
            guard_triggered=False,
            row_means=means,
            row_rms=rms,
            raw_weights=weights,
            has_negative_weight=False,
            block_summed_weights=None,
            anchor_index=None,
            anchor_weight=None,
            mask_max=None,
            would_create_mask=False,
            would_overwrite_existing_mask=False,
            existing_mask_before=existing_before,
            existing_mask_after=None if existing is None else existing.copy(),
            input_snapshot=input_snapshot,
        )

    # linecorrect.c:262-278 — in-place same-sign block summation
    blocks = weights.copy()
    block_start = 0
    for i in range(yres - 2):
        if blocks[i] * blocks[i + 1] < 0.0:
            block_sum = 0.0
            for j in range(block_start, i + 1):
                block_sum += float(blocks[j])
            for j in range(block_start, i + 1):
                blocks[j] = block_sum
            block_start = i + 1
    block_sum = 0.0
    for j in range(block_start, yres - 1):
        block_sum += float(blocks[j])
    for j in range(block_start, yres - 1):
        blocks[j] = block_sum

    # linecorrect.c:280-287 — strict-first-maximum anchor
    anchor_weight = 0.0
    anchor = 0
    for i in range(yres - 1):
        if blocks[i] > anchor_weight:
            anchor_weight = float(blocks[i])
            anchor = i

    # linecorrect.c:292-293 — mask field, all zero
    mask = np.zeros((yres, xres), dtype=np.float64, order="C")

    # linecorrect.c:296-302 — downward sign-toggle propagation
    inverted = False
    for i in range(anchor, yres - 1):
        if weights[i] < 0.0:
            inverted = not inverted
        if inverted:
            mask[i + 1, :] = 1.0

    # linecorrect.c:305-311 — upward sign-toggle propagation
    inverted = False
    for i in range(anchor, -1, -1):
        if weights[i] < 0.0:
            inverted = not inverted
        if inverted:
            mask[i, :] = 1.0

    mask_max = float(mask.max())
    would_create = mask_max > 0.0

    # linecorrect.c:315-318 — early return only for a no-existing-mask and
    # empty generated mask (unreachable when has_negative, but modelled)
    if existing is None and mask_max <= 0.0:
        return _GwydionMarkInvertedRowsResult(
            generated_mask=mask,
            global_mean=global_mean,
            global_rms=global_rms,
            guard_triggered=False,
            row_means=means,
            row_rms=rms,
            raw_weights=weights,
            has_negative_weight=True,
            block_summed_weights=blocks,
            anchor_index=anchor,
            anchor_weight=anchor_weight,
            mask_max=mask_max,
            would_create_mask=False,
            would_overwrite_existing_mask=False,
            existing_mask_before=None,
            existing_mask_after=None,
            input_snapshot=input_snapshot,
        )

    # linecorrect.c:321-327 — existing mask overwritten in place
    existing_after = None
    if existing is not None:
        existing[...] = mask
        existing_after = existing.copy()

    return _GwydionMarkInvertedRowsResult(
        generated_mask=mask,
        global_mean=global_mean,
        global_rms=global_rms,
        guard_triggered=False,
        row_means=means,
        row_rms=rms,
        raw_weights=weights,
        has_negative_weight=True,
        block_summed_weights=blocks,
        anchor_index=anchor,
        anchor_weight=anchor_weight,
        mask_max=mask_max,
        would_create_mask=would_create,
        would_overwrite_existing_mask=existing is not None,
        existing_mask_before=existing_before,
        existing_mask_after=existing_after,
        input_snapshot=input_snapshot,
    )
