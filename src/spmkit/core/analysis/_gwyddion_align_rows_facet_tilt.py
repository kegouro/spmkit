"""Private portable Gwyddion 2.71 Align Rows facet-tilt kernel.

This module intentionally implements only the source-confirmed
linematch_do_facet_tilt algorithm from the frozen Gwyddion 2.71
linematch.c source (lines 625-749).  It is not a public API and does
not emulate the installed package's compiler-specific reassociation
profile.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import ArrayLike

from ._gwyddion_align_rows_statistics import (
    FloatArray,
    _GwyddionAlignRowsDirection,
    _GwyddionMaskMode,
    _minimum_sample_count,
    _validated_enum,
    _validated_field,
    _validated_mask,
)

_C = 1.0 / 200.0


def _exp(value: float) -> float:
    """Return ``exp(value)`` matching C's ``exp()`` which returns HUGE_VAL
    (infinity) on overflow without raising an error."""
    try:
        return math.exp(value)
    except OverflowError:
        return math.inf


@dataclass(frozen=True)
class _GwyddionFacetTiltResult:
    """Corrected field with optional extracted background and zero shifts."""

    corrected: FloatArray
    background: FloatArray | None
    shifts: FloatArray


def _row_fit_facet_tilt(
    drow: FloatArray,
    mrow: FloatArray | None,
    mode: _GwyddionMaskMode,
    dx: float,
    mincount: int,
) -> float:
    """Compute one facet-tilt estimate for a single row.

    Implements the exact ``row_fit_facet_tilt`` from Gwyddion 2.71
    linematch.c.  The FP order of ``sigma2 = C * sigma2 / n`` and
    ``return sumvx/sumvz * dx`` is preserved for source parity.

    Note that for sensible inputs the computed tilt is independent of
    ``dx`` (the factor cancels in ``sumvx/sumvz * dx``).  The convergence
    test ``fabs(tilt/dx) < 1e-6`` however *does* depend on ``dx``.
    """
    res = drow.size
    sigma2 = 0.0
    n = 0

    if mrow is not None and mode is _GwyddionMaskMode.INCLUDE:
        for i in range(res - 1):
            if mrow[i] >= 1.0 and mrow[i + 1] >= 1.0:
                vx = (drow[i + 1] - drow[i]) / dx
                sigma2 += vx * vx
                n += 1
    elif mrow is not None and mode is _GwyddionMaskMode.EXCLUDE:
        for i in range(res - 1):
            if mrow[i] <= 0.0 and mrow[i + 1] <= 0.0:
                vx = (drow[i + 1] - drow[i]) / dx
                sigma2 += vx * vx
                n += 1
    else:
        for i in range(res - 1):
            vx = (drow[i + 1] - drow[i]) / dx
            sigma2 += vx * vx
        n = res - 1

    if n < mincount:
        return 0.0

    # C: sigma2 = c*sigma2/n  →  ((1.0/200.0) * sigma2) / n
    sigma2 = (_C * sigma2) / n

    sumvx = 0.0
    sumvz = 0.0
    if mrow is not None and mode is _GwyddionMaskMode.INCLUDE:
        for i in range(res - 1):
            if mrow[i] >= 1.0 and mrow[i + 1] >= 1.0:
                vx = (drow[i + 1] - drow[i]) / dx
                q = _exp(vx * vx / sigma2)
                sumvx += vx / q
                sumvz += 1.0 / q
    elif mrow is not None and mode is _GwyddionMaskMode.EXCLUDE:
        for i in range(res - 1):
            if mrow[i] <= 0.0 and mrow[i + 1] <= 0.0:
                vx = (drow[i + 1] - drow[i]) / dx
                q = _exp(vx * vx / sigma2)
                sumvx += vx / q
                sumvz += 1.0 / q
    else:
        for i in range(res - 1):
            vx = (drow[i + 1] - drow[i]) / dx
            q = _exp(vx * vx / sigma2)
            sumvx += vx / q
            sumvz += 1.0 / q

    # C: return sumvx/sumvz * dx  →  (sumvx/sumvz) * dx
    return (sumvx / sumvz) * dx


def _untilt_row(drow: FloatArray, res: int, bx: float) -> None:
    """Subtract facet tilt from a row in-place.

    ``bx == 0.0`` is a no-op (matching ``if (!bx) return`` in C).
    NaN ``bx`` is truthy, so subtraction proceeds and propagates NaN.
    """
    if bx == 0.0:
        return

    half = 0.5 * (res - 1)
    for i in range(res):
        x = i - half
        drow[i] -= bx * x


def _background_in_c_order(input_data: FloatArray, corrected: FloatArray) -> FloatArray:
    """Compute ``input - corrected`` elementwise in row-major C order."""
    background = np.empty_like(input_data, order="C")
    for row in range(input_data.shape[0]):
        for col in range(input_data.shape[1]):
            background[row, col] = input_data[row, col] - corrected[row, col]
    return background


def _gwyddion_align_rows_facet_tilt(
    data: ArrayLike,
    *,
    masking_mode: object,
    direction: object,
    dx: object,
    mask: ArrayLike | None = None,
    extract_background: object = False,
) -> _GwyddionFacetTiltResult:
    """Compute the private portable Gwyddion 2.71 facet-tilt result.

    Parameters
    ----------
    data : array-like, (yres, xres).
        Finite numeric two-dimensional input.
    masking_mode : _GwyddionMaskMode.
    direction : _GwyddionAlignRowsDirection.
    dx : float.
        Physical pixel spacing in data units (xreal / xres).  Required
        for the convergence test ``|tilt/dx| < 1e-6``.
    mask : None or (yres, xres) array-like.
    extract_background : bool.
        When True, the returned ``background`` is ``input - corrected``
        computed in row-major C order.

    Returns
    -------
    _GwyddionFacetTiltResult
    """
    values = _validated_field(data, label="data")
    validated_mask = _validated_mask(mask, values.shape)
    selected_mode = cast(
        _GwyddionMaskMode,
        _validated_enum(masking_mode, _GwyddionMaskMode, "masking_mode"),
    )
    selected_direction = cast(
        _GwyddionAlignRowsDirection,
        _validated_enum(direction, _GwyddionAlignRowsDirection, "direction"),
    )
    if isinstance(dx, (bool, np.bool_)) or not isinstance(
        dx, (int, float, np.integer, np.floating)
    ):
        raise TypeError("Gwyddion Align Rows facet_tilt dx must be a real scalar")
    dx_value = float(dx)
    if not math.isfinite(dx_value):
        raise ValueError("Gwyddion Align Rows facet_tilt dx must be finite")
    if dx_value <= 0.0:
        raise ValueError("Gwyddion Align Rows facet_tilt dx must be positive")
    if not isinstance(extract_background, (bool, np.bool_)):
        raise TypeError("Gwyddion Align Rows extract_background must be boolean")

    effective_mask = (
        None
        if validated_mask is None or selected_mode is _GwyddionMaskMode.IGNORE
        else validated_mask
    )

    if selected_direction is _GwyddionAlignRowsDirection.HORIZONTAL:
        working = values.copy(order="C")
        working_mask = effective_mask
        work_yres, work_xres = values.shape
    else:
        working = np.ascontiguousarray(values.T, dtype=np.float64)
        working_mask = (
            None
            if effective_mask is None
            else np.ascontiguousarray(effective_mask.T, dtype=np.float64)
        )
        work_yres, work_xres = working.shape

    mincount = _minimum_sample_count(work_xres)

    for row_idx in range(work_yres):
        drow = working[row_idx]
        mrow = working_mask[row_idx] if working_mask is not None else None
        for _ in range(30):
            tilt = _row_fit_facet_tilt(drow, mrow, selected_mode, dx_value, mincount)
            _untilt_row(drow, work_xres, tilt)
            if math.fabs(tilt / dx_value) < 1e-6:
                break

    corrected = (
        working
        if selected_direction is _GwyddionAlignRowsDirection.HORIZONTAL
        else np.ascontiguousarray(working.T)
    )
    background = (
        _background_in_c_order(values, corrected) if extract_background else None
    )
    shifts = np.zeros(work_yres, dtype=np.float64, order="C")
    return _GwyddionFacetTiltResult(
        corrected=corrected, background=background, shifts=shifts
    )
