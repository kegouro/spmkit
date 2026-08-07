"""Independent Python reference for Gwydion 2.71 Mark Scars.

Reproduces the numerical operation of libprocess/correct.c
(gwy_data_field_mark_scars, lines 1384-1512) together with the module-level
composition of modules/process/scars.c (mark_scars 148-169, execute 249-258,
scars_mark container semantics 232-236, sanitize_params 358-365), with the
exact source operation ordering, using only the Python standard library and
NumPy.

Independence: this module does not import any SPMKit production module, any
Gwydion-compatibility kernel, the fixture generator, or any fixture file.
It does not call Gwydion.  Expected outputs are never read from fixtures.

All inputs must be finite float64 arrays; NaN and infinities are rejected
(a deliberate future SPMKit policy difference; the Gwydion source propagates
IEEE arithmetic without pre-filtering).  The data field and existing mask
are never modified.

Polarity values follow the source enum (scars.c:39-43):
FEATURES_POSITIVE = 1, FEATURES_NEGATIVE = 4, FEATURES_BOTH = 3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray

POSITIVE = 1
NEGATIVE = 4
BOTH = 3

UNION = 0      # GWY_MERGE_UNION
INTERSECTION = 1  # GWY_MERGE_INTERSECTION


def _validated_field(value: object, *, operation: str) -> np.ndarray:
    source = np.asarray(value, dtype=np.float64)
    if source.ndim != 2:
        raise ValueError(f"{operation} data must be two-dimensional")
    if 0 in source.shape:
        raise ValueError(f"{operation} data must have non-empty dimensions")
    if not np.isfinite(source).all():
        raise ValueError(f"{operation} data must be finite")
    return np.array(source, dtype=np.float64, order="C", copy=True)


def _validated_mask(value: object, shape: tuple[int, int],
                    *, operation: str) -> np.ndarray:
    mask = _validated_field(value, operation=operation)
    if mask.shape != shape:
        raise ValueError(f"{operation} mask shape must match data")
    return mask


def _vertical_rms(field: np.ndarray) -> float:
    """Global vertical-difference RMS with the source denominator.

    correct.c:1413-1424: sequential sum of squared vertical neighbour
    differences over i in 0..yres-2, j in 0..xres-1, divided by xres*yres
    (the full pixel count, not the difference count).
    """
    yres, xres = field.shape
    total = 0.0
    for i in range(yres - 1):
        row = field[i]
        nxt = field[i + 1]
        for j in range(xres):
            z = row[j] - nxt[j]
            total += z * z
    return math.sqrt(total / (xres * yres))


def _detector_pass(field: np.ndarray, threshold_low: float,
                   threshold_high: float, min_len: int, max_width: int,
                   negative: bool, rms: float) -> np.ndarray:
    """One gwy_data_field_mark_scars execution (correct.c:1384-1512).

    Returns the final binary mask (0.0/1.0).  The initial search uses
    threshold_low for detection and threshold_high for hard seeds; the
    expansion attaches soft pixels to hard runs; the final pass keeps only
    runs of length >= min_len and clamps them to 1.0.  ``rms`` is the
    precomputed global vertical-difference RMS used both in the detection
    comparison and the weight normalization.
    """
    yres, xres = field.shape
    mask = np.zeros((yres, xres), dtype=np.float64)
    thr = threshold_low * rms

    # initial scar search (correct.c:1429-1471)
    for i in range(yres - (max_width + 1)):
        for j in range(xres):
            row = field[i:, j]  # rows i .. i+max_width+1
            detected_k = 0
            if negative:
                top = row[0]
                bottom = row[1]
                for k in range(1, max_width + 1):
                    top = min(row[0], row[k + 1])
                    bottom = max(bottom, row[k])
                    if top - bottom >= thr:
                        detected_k = k
                        break
                if detected_k:
                    for kk in range(detected_k, 0, -1):
                        w = (top - row[kk]) / rms
                        mask[i + kk, j] = np.fmax(mask[i + kk, j], w)
            else:
                bottom = row[0]
                top = row[1]
                for k in range(1, max_width + 1):
                    bottom = max(row[0], row[k + 1])
                    top = min(top, row[k])
                    if top - bottom >= thr:
                        detected_k = k
                        break
                if detected_k:
                    for kk in range(detected_k, 0, -1):
                        w = (row[kk] - bottom) / rms
                        mask[i + kk, j] = np.fmax(mask[i + kk, j], w)

    # expand high threshold to neighbouring low threshold (1472-1484)
    for i in range(yres):
        mrow = mask[i]
        for j in range(1, xres):
            if mrow[j] >= threshold_low and mrow[j - 1] >= threshold_high:
                mrow[j] = threshold_high
        for j in range(xres - 1, 0, -1):
            if mrow[j - 1] >= threshold_low and mrow[j] >= threshold_high:
                mrow[j - 1] = threshold_high

    # kill too short segments, clamping to 1.0 (1485-1511)
    for i in range(yres):
        mrow = mask[i]
        k = 0
        for j in range(xres):
            if mrow[j] >= threshold_high:
                mrow[j] = 1.0
                k += 1
                continue
            if k and k < min_len:
                for kk in range(1, k + 1):
                    mrow[j - kk] = 0.0
            mrow[j] = 0.0
            k = 0
        if k and k < min_len:
            for kk in range(1, k + 1):
                mrow[xres - kk] = 0.0
    return mask


@dataclass(frozen=True)
class MarkScarsReference:
    """Every observable of the source Mark Scars operation."""

    input_snapshot: FloatArray
    effective_threshold_high: float
    effective_threshold_low: float
    effective_min_length: int
    effective_max_width: int
    polarity: int
    vertical_rms: float
    positive_kernel_mask: FloatArray | None
    negative_kernel_mask: FloatArray | None
    final_module_mask: FloatArray
    existing_mask_before: FloatArray | None
    mask_present: bool
    nonzero_count: int
    marked_runs: tuple[tuple[int, int, int], ...]
    guard_triggered: bool
    guard_reason: str | None

    def kernel_mask(self) -> FloatArray:
        """The combined detector mask for the executed polarity."""
        return self.final_module_mask


def oracle_mark_scars(
    field: object,
    *,
    threshold_high: float = 0.666,
    threshold_low: float = 0.25,
    min_length: int = 16,
    max_width: int = 4,
    polarity: int = BOTH,
    existing_mask: object | None = None,
    combine: bool = False,
    combine_type: int = UNION,
) -> MarkScarsReference:
    """Run the independent Mark Scars reference.

    The sanitization order follows the source: module sanitize_params
    (scars.c:358-365) then kernel clamps (correct.c:1407-1409):
      threshold_high = MAX(threshold_high, threshold_low)
      min_length    = MAX(min_length, 1)
      max_width     = MIN(max_width, yres - 2)
    Early returns (empty mask) follow correct.c:1410-1411 and 1425-1426.
    """
    data = _validated_field(field, operation="Mark Scars")
    yres, xres = data.shape
    existing = (None if existing_mask is None
                else _validated_mask(existing_mask, data.shape,
                                     operation="Mark Scars"))
    if polarity not in (POSITIVE, NEGATIVE, BOTH):
        raise ValueError("polarity must be 1 (positive), 4 (negative) or 3 (both)")

    # sanitization (module then kernel, both max operations)
    high = max(threshold_high, threshold_low)
    low = threshold_low
    min_len = max(min_length, 1)
    max_width_k = min(max_width, yres - 2)

    guard_reason = None
    if min_len > xres:
        guard_reason = "min_length > xres"
    elif max_width_k < 1:
        guard_reason = "max_width < 1"
    elif low <= 0.0:
        guard_reason = "threshold_low <= 0"
    if guard_reason is None:
        rms = _vertical_rms(data)
        if rms == 0.0:
            guard_reason = "vertical rms == 0"

    pos_mask: FloatArray | None = None
    neg_mask: FloatArray | None = None
    final: FloatArray = np.zeros((yres, xres), dtype=np.float64)

    if guard_reason is not None:
        rms = _vertical_rms(data) if guard_reason != "vertical rms == 0" else 0.0
    else:
        if polarity in (POSITIVE, BOTH):
            pos_mask = _detector_pass(data, low, high, min_len, max_width_k,
                                      negative=False, rms=rms)
        if polarity in (NEGATIVE, BOTH):
            neg_mask = _detector_pass(data, low, high, min_len, max_width_k,
                                      negative=True, rms=rms)
        if polarity == BOTH:
            assert pos_mask is not None and neg_mask is not None
            final = np.fmax(pos_mask, neg_mask)   # scars.c:167 max_of_fields
        else:
            selected = pos_mask if pos_mask is not None else neg_mask
            assert selected is not None
            final = selected

    # module-level combine with an existing mask (scars.c:249-258)
    if existing is not None and combine:
        if combine_type == UNION:
            final = np.fmax(final, existing)
        elif combine_type == INTERSECTION:
            final = np.fmin(final, existing)
        else:
            raise ValueError("combine_type must be 0 (union) or 1 (intersection)")

    # no-detection container classification (scars.c:233-236)
    mask_present = bool(float(np.max(final)) > 0.0)
    nonzero = int(np.count_nonzero(final))
    runs: list[tuple[int, int, int]] = []
    for i in range(yres):
        j = 0
        while j < xres:
            if final[i, j] != 0.0:
                start = j
                while j < xres and final[i, j] != 0.0:
                    j += 1
                runs.append((i, start, j - start))
            else:
                j += 1

    return MarkScarsReference(
        input_snapshot=data,
        effective_threshold_high=high,
        effective_threshold_low=low,
        effective_min_length=min_len,
        effective_max_width=max_width_k,
        polarity=polarity,
        vertical_rms=rms,
        positive_kernel_mask=pos_mask,
        negative_kernel_mask=neg_mask,
        final_module_mask=final,
        existing_mask_before=existing,
        mask_present=mask_present,
        nonzero_count=nonzero,
        marked_runs=tuple(runs),
        guard_triggered=guard_reason is not None,
        guard_reason=guard_reason,
    )
