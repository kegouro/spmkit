"""Gwydion 2.71 scan-line defect capabilities: Step Line Correction and
Mark Inverted Rows.

Public compatibility APIs backed by private production kernels that
reproduce the frozen Gwydion 2.71 numerical operations (source-inclusion
compiled probe, independent oracle, frozen fixtures) within the validated
finite-input scope.  Horizontal row processing only; no direction, mask,
threshold or filter parameters are accepted.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

import numpy as np

from spmkit.core.analysis._gwydion_mark_inverted_rows import (
    _gwydion_mark_inverted_rows_result,
)
from spmkit.core.analysis._gwydion_mark_scars import (
    _gwydion_mark_scars_result,
)
from spmkit.core.analysis._gwydion_remove_scars import (
    _gwydion_remove_scars_result,
)
from spmkit.core.analysis._gwydion_step_line_correction import (
    _gwydion_step_line_correction_result,
)

if TYPE_CHECKING:
    from spmkit.core.models.spmdata import SPMChannel

FloatArray = np.ndarray


def _validated_channel_data(channel: SPMChannel, *, operation: str) -> FloatArray:
    """Validate channel data for the scan-line operations.

    Requires a non-empty two-dimensional finite numeric field; NaN and
    infinities are rejected (a deliberate SPMKit policy difference from the
    Gwydion source, which propagates IEEE arithmetic without pre-filtering).
    """
    data = np.asarray(channel.data)
    if data.ndim != 2:
        raise ValueError(f"{operation} requires a two-dimensional channel")
    if data.size == 0:
        raise ValueError(f"{operation} requires non-empty data")
    if not np.issubdtype(data.dtype, np.number) or np.iscomplexobj(data):
        raise TypeError(f"{operation} requires real numeric data")
    if not np.all(np.isfinite(data)):
        raise ValueError(f"{operation} requires finite data")
    return np.array(data, dtype=np.float64, order="C", copy=True)


def gwydion_step_line_correction(channel: SPMChannel) -> SPMChannel:
    """Apply the frozen Gwydion 2.71 Step Line Correction operation.

    The operation aligns rows by upper-median row statistics, runs two
    passes of the step detector (v = (middle-top)*(middle-bottom) >
    3.0*w, segments of at least 4 equal-sign pixels, correction
    (3*segment_residual + local_residual)/4), applies the size-5
    conservative denoise filter (numerical no-op for any dimension below
    5), and restores the original global mean.  It is an aggressive and
    potentially destructive transformation.

    ``channel`` data must be non-empty, two-dimensional, real and finite
    (NaN/Inf rejected).  The operation is horizontal-only and accepts no
    direction, mask, threshold or filter parameters.  The input channel is
    not mutated; a new ``SPMChannel`` with the input context preserved
    (shape, ranges, units, copied metadata) is returned.
    """
    data = _validated_channel_data(channel, operation="Step Line Correction")
    corrected = _gwydion_step_line_correction_result(data, trace=False)
    assert isinstance(corrected, np.ndarray)
    return channel.with_data(corrected)


def gwydion_mark_inverted_rows(channel: SPMChannel) -> FloatArray:
    """Mark rows whose sign is inverted relative to their neighbours.

    The frozen Gwydion 2.71 operation classifies rows from the sign of
    adjacent-row correlation weights
    (sum((x-mean_a)*(y-mean_b)) / (rms_a*rms_b + total_rms**2)), anchors at
    the most positively correlated block (strict first maximum) and toggles
    inversion only at strictly negative weights.  It never modifies the data
    field.

    ``channel`` data must be non-empty, two-dimensional, real and finite
    (NaN/Inf rejected).  The operation is horizontal-only and accepts no
    direction or threshold parameters.

    Returns a new C-contiguous float64 mask with the channel shape and
    values exactly 0.0 or 1.0 (1.0 on inverted rows).  SPMKit deliberately
    has no persistent channel mask state: the mask is returned as an
    independent array, and source paths that would not create a mask map to
    an all-zero returned mask.  The input channel is never mutated.
    """
    data = _validated_channel_data(channel, operation="Mark Inverted Rows")
    result = _gwydion_mark_inverted_rows_result(data, existing_mask=None)
    if result.generated_mask is None:
        return np.zeros(data.shape, dtype=np.float64, order="C")
    return np.array(result.generated_mask, dtype=np.float64, order="C", copy=True)


GwyddionScarPolarity = Literal["positive", "negative", "both"]
"""Polarity selector for :func:`gwydion_mark_scars` and
:func:`gwydion_remove_scars`, mirroring the Gwyddion process-module enum
(POSITIVE = 1, NEGATIVE = 4, BOTH = 3)."""

GwyddionMaskCombineMode = Literal["replace", "union", "intersection"]
"""Combination mode of a Mark Scars detector result with an existing mask
(replace ignores the existing mask; union is source-compatible fmax;
intersection is source-compatible fmin)."""


def gwydion_mark_scars(
    channel: SPMChannel,
    *,
    threshold_high: float = 0.666,
    threshold_low: float = 0.25,
    min_length: int = 16,
    max_width: int = 4,
    polarity: GwyddionScarPolarity = "both",
    existing_mask: np.ndarray | None = None,
    combine: GwyddionMaskCombineMode = "replace",
) -> np.ndarray:
    """Mark horizontal scan-line scars in a channel (frozen Gwydion 2.71).

    The detector computes a single global vertical-difference RMS
    (sum of squared vertical neighbour differences divided by xres*yres),
    searches per column for bands up to ``max_width`` rows whose values lie
    at least ``threshold_low`` RMS away from their boundary rows, keeps
    pixels with weight at least ``threshold_high`` RMS as hard seeds,
    attaches adjacent soft pixels through chained horizontal expansion and
    retains only per-row runs of at least ``min_length`` pixels.  Positive
    scars are bands elevated above their neighbours; negative scars are
    depressed bands; ``"both"`` runs the two detectors and unions the
    binary masks.  This is a detector, not proof of physical corruption.

    ``channel`` data must be non-empty, two-dimensional, real and finite.
    Parameter domains match the Gwyddion process module: thresholds finite
    within [0.0, 2.0], ``min_length`` within [1, 1024], ``max_width``
    within [1, 16].  When ``threshold_low > threshold_high`` the effective
    hard threshold becomes ``threshold_low`` (source sanitization).

    ``existing_mask`` (when given) must be finite, two-dimensional and
    shape-compatible; it is never mutated.  ``combine="replace"`` ignores
    it; ``"union"`` (fmax) and ``"intersection"`` (fmin) require it.
    Combined masks may retain finite non-binary values originating from the
    existing mask; only the bare detector output is exactly binary 0.0/1.0.

    The input channel is never mutated.  A no-detection replace result is
    an all-zero returned mask; SPMKit does not simulate Data Browser mask
    removal or persistence.

    Returns a new C-contiguous float64 mask with the channel shape.
    """
    data = _validated_channel_data(channel, operation="Mark Scars")
    if not math.isfinite(threshold_high) or not 0.0 <= threshold_high <= 2.0:
        raise ValueError("threshold_high must be finite and within [0.0, 2.0]")
    if not math.isfinite(threshold_low) or not 0.0 <= threshold_low <= 2.0:
        raise ValueError("threshold_low must be finite and within [0.0, 2.0]")
    if not isinstance(min_length, int) or isinstance(min_length, bool):
        raise TypeError("min_length must be an integer")
    if not 1 <= min_length <= 1024:
        raise ValueError("min_length must be within [1, 1024]")
    if not isinstance(max_width, int) or isinstance(max_width, bool):
        raise TypeError("max_width must be an integer")
    if not 1 <= max_width <= 16:
        raise ValueError("max_width must be within [1, 16]")
    if polarity not in ("positive", "negative", "both"):
        raise ValueError("polarity must be 'positive', 'negative' or 'both'")
    if combine not in ("replace", "union", "intersection"):
        raise ValueError("combine must be 'replace', 'union' or 'intersection'")
    if combine != "replace" and existing_mask is None:
        raise ValueError("union/intersection require an existing mask")
    result = _gwydion_mark_scars_result(
        data,
        threshold_high=threshold_high,
        threshold_low=threshold_low,
        min_length=min_length,
        max_width=max_width,
        polarity=polarity,
        existing_mask=existing_mask,
        combine=combine,
    )
    return np.array(result.final_mask, dtype=np.float64, order="C", copy=True)


def gwydion_remove_scars(
    channel: SPMChannel,
    *,
    threshold_high: float = 0.666,
    threshold_low: float = 0.25,
    min_length: int = 16,
    max_width: int = 4,
    polarity: GwyddionScarPolarity = "both",
) -> SPMChannel:
    """Remove horizontal scan-line scars (frozen Gwydion 2.71 composition).

    Exactly composes the Mark Scars detector (with the same parameter
    semantics as :func:`gwydion_mark_scars`) and the Laplace interpolation
    of :func:`spmkit.core.analysis.interpolation.gwydion_interpolate_data_under_mask`.
    The detector mask is a private temporary mask: it is never exposed,
    never mutated and never stored.  No extra hidden correction is applied.

    ``channel`` data must be non-empty, two-dimensional, real and finite.
    The input channel is never mutated; a new ``SPMChannel`` preserving the
    input context (shape, ranges, units, copied metadata) is returned.
    Detected/interpolated values are not claimed to be physically
    recovered.
    """
    data = _validated_channel_data(channel, operation="Remove Scars")
    if not math.isfinite(threshold_high) or not 0.0 <= threshold_high <= 2.0:
        raise ValueError("threshold_high must be finite and within [0.0, 2.0]")
    if not math.isfinite(threshold_low) or not 0.0 <= threshold_low <= 2.0:
        raise ValueError("threshold_low must be finite and within [0.0, 2.0]")
    if not isinstance(min_length, int) or isinstance(min_length, bool):
        raise TypeError("min_length must be an integer")
    if not 1 <= min_length <= 1024:
        raise ValueError("min_length must be within [1, 1024]")
    if not isinstance(max_width, int) or isinstance(max_width, bool):
        raise TypeError("max_width must be an integer")
    if not 1 <= max_width <= 16:
        raise ValueError("max_width must be within [1, 16]")
    if polarity not in ("positive", "negative", "both"):
        raise ValueError("polarity must be 'positive', 'negative' or 'both'")
    result = _gwydion_remove_scars_result(
        data,
        threshold_high=threshold_high,
        threshold_low=threshold_low,
        min_length=min_length,
        max_width=max_width,
        polarity=polarity,
    )
    return channel.with_data(result.corrected_field)
