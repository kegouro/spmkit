"""Gwydion 2.71 scan-line defect capabilities: Step Line Correction and
Mark Inverted Rows.

Public compatibility APIs backed by private production kernels that
reproduce the frozen Gwydion 2.71 numerical operations (source-inclusion
compiled probe, independent oracle, frozen fixtures) within the validated
finite-input scope.  Horizontal row processing only; no direction, mask,
threshold or filter parameters are accepted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from spmkit.core.analysis._gwydion_mark_inverted_rows import (
    _gwydion_mark_inverted_rows_result,
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
