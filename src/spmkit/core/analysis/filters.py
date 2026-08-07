"""Public Gwydion 2.71 neighborhood-filter operations.

Implements the three A2 neighborhood-filter public APIs:

  * gwyddion_rank_filter
  * gwyddion_median_filter
  * gwyddion_gaussian_filter

Each operation applies the frozen compiled-profile kernel
(COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION)
to one finite two-dimensional SPMChannel and returns a new context-
preserving SPMChannel.  The input channel and data are never mutated.

Source/version attribution (behavioral): Gwydion 2.71
modules/process/rank-filter.c, modules/tools/filter.c,
libprocess/filters-minmax.c, libprocess/elliptic.c,
libprocess/filters-convdeconv.c.
"""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis._gwyddion_neighborhood_filters import (
    _gwydion_gaussian_filter,
    _gwydion_median_filter,
    _gwydion_rank_filter,
)
from spmkit.core.models.spmdata import SPMChannel


def _channel_result(channel: SPMChannel, corrected: np.ndarray) -> SPMChannel:
    if not isinstance(channel, SPMChannel):
        raise TypeError("Gwydion neighborhood filter requires an SPMChannel")
    return channel.with_data(corrected)


def gwyddion_rank_filter(
    channel: SPMChannel,
    *,
    radius: int = 20,
    percentile: float = 0.75,
) -> SPMChannel:
    """Apply the Gwydion 2.71 Rank Filter (primary percentile only).

    ``radius`` is the pixel radius in ``1..1024``; the footprint is the
    ellipse inscribed in a ``2*radius+1`` square.  ``percentile`` in
    ``0..1`` selects the rank ``GWY_ROUND(percentile*(n-1))`` of the
    neighborhood values, where ``n`` is the active footprint count;
    percentile 0 is the local minimum and percentile 1 the local maximum.
    Borders use nearest-constant EXTEND extension.  The result is a new
    context-preserving ``SPMChannel``; the input is never mutated.
    """
    result = _gwydion_rank_filter(
        channel.data, radius=radius, percentile=percentile)
    return _channel_result(channel, result.result)


def gwyddion_median_filter(
    channel: SPMChannel,
    *,
    size: int = 5,
) -> SPMChannel:
    """Apply the Gwydion 2.71 disc Median Filter.

    ``size`` is the footprint SIDE in ``2..31`` (not a radius); even sizes
    are valid.  The footprint is the ellipse inscribed in the ``size x
    size`` square and the median is the upper median (rank ``n//2``).
    Borders use nearest-constant EXTEND extension.  The result is a new
    context-preserving ``SPMChannel``; the input is never mutated.
    """
    result = _gwydion_median_filter(channel.data, size=size)
    return _channel_result(channel, result.result)


def gwyddion_gaussian_filter(
    channel: SPMChannel,
    *,
    sigma: float = 5.0,
) -> SPMChannel:
    """Apply the Gwydion 2.71 Gaussian Filter.

    ``sigma`` is in pixels and must be in ``0.01..40.0`` (sigma=0 is
    library-domain evidence and is rejected publicly).  The separable
    kernel resolution is ``2*ceil(5*sigma)+1`` capped at
    ``3*min(xres, yres)`` and forced odd; borders use mirror extension.
    Kernel normalization follows the source sequential summation and is
    not forced to exactly 1.0, so constant-field drift at the
    normalization rounding level (~1e-15) is preserved.  The result is a
    new context-preserving ``SPMChannel``; the input is never mutated.
    """
    result = _gwydion_gaussian_filter(channel.data, sigma=sigma, public=True)
    return _channel_result(channel, result.result)
