"""Public Gwydion 2.71 Laplace interpolation (Interpolate Data Under Mask).

The Laplace interpolation is not scan-line specific: it substitutes data
under a mask by the solution of the discrete Laplace equation with
Dirichlet data from the surrounding unmasked pixels and Neumann conditions
at image borders, following the frozen Gwydion 2.71 contract of
gwy_data_field_laplace_solve(field, mask, -1, 1.0).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from spmkit.core.analysis._gwydion_laplace import _gwydion_laplace_result

if TYPE_CHECKING:
    from spmkit.core.models.spmdata import SPMChannel

FloatArray = np.ndarray


def _validated_channel_data(channel: SPMChannel, *, operation: str) -> FloatArray:
    source = np.asarray(channel.data)
    if source.ndim != 2:
        raise ValueError(f"{operation} requires a two-dimensional channel")
    if source.size == 0:
        raise ValueError(f"{operation} requires non-empty data")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError(f"{operation} requires real numeric data")
    if not np.all(np.isfinite(source)):
        raise ValueError(f"{operation} requires finite data")
    return np.array(source, dtype=np.float64, order="C", copy=True)


def gwydion_interpolate_data_under_mask(
    channel: SPMChannel,
    mask: np.ndarray,
) -> SPMChannel:
    """Interpolate data under a mask by the Laplace equation solution.

    Pixels with ``mask > 0.0`` are solved from the discrete Laplace
    equation: each masked pixel equals the mean of its masked neighbours
    and its fixed (unmasked) neighbours, with missing neighbours at image
    borders implementing Neumann conditions.  Mask values ``<= 0.0`` remain
    fixed and bitwise unchanged.  An empty mask returns an independent
    channel with bitwise-identical data; a whole-field positive mask
    returns the source-defined all-zero field.  Physical ``x_range`` /
    ``y_range`` do not alter the numerical solve (pixel-index based).

    ``channel`` data and ``mask`` must be finite, two-dimensional and
    shape-compatible.  The input channel and the mask are never mutated; a
    new ``SPMChannel`` preserving the input context (shape, ranges, units,
    copied metadata) is returned.

    This API corresponds to the process operation with grain_id=-1 and
    qprec=1.0; there is no public qprec parameter.  No uncertainty, physical
    reconstruction or statistical neutrality is claimed for the
    interpolated values.
    """
    data = _validated_channel_data(channel,
                                   operation="Interpolate Data Under Mask")
    if mask.ndim != 2:
        raise ValueError("Interpolate Data Under Mask requires a "
                         "two-dimensional mask")
    if mask.size == 0:
        raise ValueError("Interpolate Data Under Mask requires non-empty mask")
    if not np.issubdtype(mask.dtype, np.number) or np.iscomplexobj(mask):
        raise TypeError("Interpolate Data Under Mask requires a real numeric mask")
    if not np.all(np.isfinite(mask)):
        raise ValueError("Interpolate Data Under Mask requires a finite mask")
    if mask.shape != data.shape:
        raise ValueError("Interpolate Data Under Mask mask shape must match "
                         "the channel")
    result = _gwydion_laplace_result(data, mask)
    return channel.with_data(result.corrected_field)
