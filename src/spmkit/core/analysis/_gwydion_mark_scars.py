"""Production kernel: Gwydion 2.71 Mark Scars (finite-input scope).

Implements the frozen numerical contract of libprocess/correct.c
(gwy_data_field_mark_scars, lines 1384-1512) together with the module-level
composition of modules/process/scars.c (mark_scars 148-169, execute
249-258, sanitize_params 358-365), with the exact source operation order.

Independence: this module does not import tests, fixtures, oracles, the
fixture generator, or Gwydion.  It is written independently from the frozen
numerical contract; parity was established by the compiled-probe campaign
and frozen fixtures.

SPMKit policy differences (documented): NaN/Inf inputs are rejected here,
while the Gwydion source propagates IEEE arithmetic without pre-filtering;
the Data Browser container semantics (mask removal/persistence) are not
simulated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray

POSITIVE = 1
NEGATIVE = 4
BOTH = 3

UNION = 0
INTERSECTION = 1

_POLARITY_TO_ENUM = {
    "positive": POSITIVE,
    "negative": NEGATIVE,
    "both": BOTH,
}
_COMBINE_TO_ENUM = {
    "replace": None,
    "union": UNION,
    "intersection": INTERSECTION,
}

def _validated_field(value: object, *, operation: str) -> np.ndarray:
    source = np.asarray(value, dtype=np.float64)
    if source.ndim != 2:
        raise ValueError(f"{operation} requires a two-dimensional channel")
    if 0 in source.shape:
        raise ValueError(f"{operation} requires non-empty data")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError(f"{operation} requires real numeric data")
    if not np.all(np.isfinite(source)):
        raise ValueError(f"{operation} requires finite data")
    return np.array(source, dtype=np.float64, order="C", copy=True)


def _validated_existing_mask(value: object, shape: tuple[int, int],
                             *, operation: str) -> np.ndarray:
    mask = _validated_field(value, operation=operation)
    if mask.shape != shape:
        raise ValueError(f"{operation} existing mask shape must match the channel")
    return mask


def _vertical_rms(field: np.ndarray) -> float:
    """Global vertical-difference RMS (correct.c:1413-1424).

    Sequential row-major sum of squared vertical neighbour differences,
    divided by xres*yres (the full pixel count, not the difference count).
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

    Returns the final binary mask (0.0/1.0).  The initial search detects
    bands at threshold_low; weights are accumulated with C fmax semantics
    (np.fmax matches C fmax including signed-zero and NaN behaviour); hard
    seeds are pixels with weight >= threshold_high; soft pixels attached
    through chained forward/backward in-place expansion; the final pass
    keeps per-row runs of length >= min_len and clamps them to 1.0.
    """
    yres, xres = field.shape
    mask = np.zeros((yres, xres), dtype=np.float64)
    thr = threshold_low * rms

    # initial scar search (correct.c:1429-1471), per-column
    # first-qualifying-width band search, source loop order
    for i in range(yres - (max_width + 1)):
        for j in range(xres):
            row = field[i:, j]
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

    # expand high threshold to neighbouring low threshold (1472-1484):
    # chained forward then backward in-place passes per row
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


def _marked_runs(mask: np.ndarray) -> tuple[tuple[int, int, int], ...]:
    runs: list[tuple[int, int, int]] = []
    yres, xres = mask.shape
    for i in range(yres):
        j = 0
        while j < xres:
            if mask[i, j] != 0.0:
                start = j
                while j < xres and mask[i, j] != 0.0:
                    j += 1
                runs.append((i, start, j - start))
            else:
                j += 1
    return tuple(runs)


@dataclass(frozen=True)
class _GwydionMarkScarsResult:
    """Every observable of the source Mark Scars operation."""

    input_snapshot: FloatArray
    effective_threshold_high: float
    effective_threshold_low: float
    effective_min_length: int
    effective_max_width: int
    polarity_enum: int
    vertical_rms: float
    positive_detector_mask: FloatArray | None
    negative_detector_mask: FloatArray | None
    combined_detector_mask: FloatArray
    existing_mask_before: FloatArray | None
    final_mask: FloatArray
    mask_present: bool
    nonzero_count: int
    marked_runs: tuple[tuple[int, int, int], ...]
    guard_triggered: bool
    guard_reason: str | None
    input_mutation_evidence: bool


def _gwydion_mark_scars_result(
    field: object,
    *,
    threshold_high: float = 0.666,
    threshold_low: float = 0.25,
    min_length: int = 16,
    max_width: int = 4,
    polarity: str = "both",
    existing_mask: object | None = None,
    combine: str = "replace",
) -> _GwydionMarkScarsResult:
    """Run the production Mark Scars kernel (private; public wrapper in
    core.analysis.scanline).

    Sanitization follows the source order: module sanitize_params
    (scars.c:358-365) then kernel clamps (correct.c:1407-1409):
    threshold_high = MAX(threshold_high, threshold_low);
    min_length = MAX(min_length, 1); max_width = MIN(max_width, yres - 2).
    Guards follow correct.c:1410-1411 and 1425-1426.
    """
    data = _validated_field(field, operation="Mark Scars")
    yres, xres = data.shape

    if polarity not in _POLARITY_TO_ENUM:
        raise ValueError("polarity must be 'positive', 'negative' or 'both'")
    if combine not in _COMBINE_TO_ENUM:
        raise ValueError("combine must be 'replace', 'union' or 'intersection'")
    combine_enum = _COMBINE_TO_ENUM[combine]
    if combine_enum is not None and existing_mask is None:
        raise ValueError("union/intersection require an existing mask")

    # SPMKit policy: finite parameters (the Gwydion source accepts any
    # doubles; the public wrapper additionally enforces the process-module
    # domains [0,2] / [1,1024] / [1,16])
    if not math.isfinite(threshold_high) or not math.isfinite(threshold_low):
        raise ValueError("thresholds must be finite")
    if not isinstance(min_length, int) or isinstance(min_length, bool):
        raise TypeError("min_length must be an integer")
    if not isinstance(max_width, int) or isinstance(max_width, bool):
        raise TypeError("max_width must be an integer")

    existing = (None if existing_mask is None else
                _validated_existing_mask(existing_mask, data.shape,
                                         operation="Mark Scars"))

    # sanitization (module then kernel, both max operations)
    high = max(threshold_high, threshold_low)
    low = threshold_low
    min_len = max(min_length, 1)
    max_width_k = min(max_width, yres - 2)

    guard_reason: str | None = None
    if min_len > xres:
        guard_reason = "min_length > xres"
    elif max_width_k < 1:
        guard_reason = "max_width < 1 after clamp"
    elif low <= 0.0:
        guard_reason = "threshold_low <= 0"
    if guard_reason is None:
        rms = _vertical_rms(data)
        if rms == 0.0:
            guard_reason = "vertical rms == 0"
    else:
        rms = 0.0

    polarity_enum = _POLARITY_TO_ENUM[polarity]
    pos_mask: FloatArray | None = None
    neg_mask: FloatArray | None = None
    if guard_reason is None:
        if polarity_enum in (POSITIVE, BOTH):
            pos_mask = _detector_pass(data, low, high, min_len, max_width_k,
                                      negative=False, rms=rms)
        if polarity_enum in (NEGATIVE, BOTH):
            neg_mask = _detector_pass(data, low, high, min_len, max_width_k,
                                      negative=True, rms=rms)
        if polarity_enum == BOTH:
            # scars.c:164-168: two detector executions plus fmax union
            assert pos_mask is not None and neg_mask is not None
            combined = np.fmax(pos_mask, neg_mask)
        else:
            selected = pos_mask if pos_mask is not None else neg_mask
            assert selected is not None
            combined = selected
    else:
        combined = np.zeros((yres, xres), dtype=np.float64)

    # module-level combine with an existing mask (scars.c:249-258)
    final = combined
    if existing is not None and combine_enum is not None:
        if combine_enum == UNION:
            final = np.fmax(combined, existing)
        else:
            final = np.fmin(combined, existing)

    # no-detection container classification (scars.c:233-236); SPMKit does
    # not simulate Data Browser mask removal or persistence
    mask_present = bool(float(np.max(final)) > 0.0)
    nonzero = int(np.count_nonzero(final))

    return _GwydionMarkScarsResult(
        input_snapshot=data,
        effective_threshold_high=high,
        effective_threshold_low=low,
        effective_min_length=min_len,
        effective_max_width=max_width_k,
        polarity_enum=polarity_enum,
        vertical_rms=rms,
        positive_detector_mask=pos_mask,
        negative_detector_mask=neg_mask,
        combined_detector_mask=combined,
        existing_mask_before=existing,
        final_mask=final,
        mask_present=mask_present,
        nonzero_count=nonzero,
        marked_runs=_marked_runs(final),
        guard_triggered=guard_reason is not None,
        guard_reason=guard_reason,
        input_mutation_evidence=False,
    )
