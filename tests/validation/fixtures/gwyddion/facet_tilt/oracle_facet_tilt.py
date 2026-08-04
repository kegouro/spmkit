"""Independent mathematical reference for Gwyddion 2.71 row_fit_facet_tilt.

This is an independent mathematical reference, not a line-by-line
translation of the Gwyddion C source.  Operation ordering is preserved
only where required for FP parity.

The reference implements the exact Gwyddion 2.71 facet-tilt algorithm
as documented in linematch.c functions row_fit_facet_tilt, untilt_row,
and linematch_do_facet_tilt (lines 625-749).  All FP behaviour follows
IEEE 754 semantics and matches the C source operation ordering where
it matters for reproducibility.
"""

import math
from typing import Literal

import numpy as np

_C = 1.0 / 200.0


def _row_fit_facet_tilt(
    drow: np.ndarray,
    mrow: np.ndarray | None,
    masking_mode: Literal["include", "exclude", "ignore"],
    dx: float,
    mincount: int,
) -> float:
    """Compute one facet-tilt estimate for a single row.

    Parameters
    ----------
    drow : 1-D float64 array, length xres.
        Row pixel data (mutable view inside the caller's buffer).
    mrow : 1-D float64 array or None.
        Mask row, same length as ``drow``.
    masking_mode : str
        ``"include"``, ``"exclude"``, or ``"ignore"``.
    dx : float
        Physical pixel spacing in data units (xreal / xres).
    mincount : int
        Minimum valid pixel-pair count to attempt a tilt fit.

    Returns
    -------
    tilt : float
        Estimated tilt (slope * dx) for this row.  Returns 0.0 when
        the usable pixel-pair count is below ``mincount``.  May return
        NaN when the row variance is zero (IEEE divide-by-zero in
        ``exp(vx² / 0)``).
    """
    res = drow.size
    sigma2 = 0.0
    n = 0

    # ---- first pass: compute robust variance sigma2 ----
    if mrow is not None and masking_mode == "include":
        for i in range(res - 1):
            if mrow[i] >= 1.0 and mrow[i + 1] >= 1.0:
                vx = (drow[i + 1] - drow[i]) / dx
                sigma2 += vx * vx
                n += 1
    elif mrow is not None and masking_mode == "exclude":
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

    # C computes: sigma2 = c * sigma2 / n  →  ((1.0/200.0) * sigma2) / n
    sigma2 = (_C * sigma2) / n  # pyright: ignore[reportOperatorPrecedence]

    # ---- second pass: weighted tilt estimate ----
    sumvx = 0.0
    sumvz = 0.0
    if mrow is not None and masking_mode == "include":
        for i in range(res - 1):
            if mrow[i] >= 1.0 and mrow[i + 1] >= 1.0:
                vx = (drow[i + 1] - drow[i]) / dx
                q = _safe_exp(vx * vx / sigma2)
                sumvx += vx / q
                sumvz += 1.0 / q
    elif mrow is not None and masking_mode == "exclude":
        for i in range(res - 1):
            if mrow[i] <= 0.0 and mrow[i + 1] <= 0.0:
                vx = (drow[i + 1] - drow[i]) / dx
                q = _safe_exp(vx * vx / sigma2)
                sumvx += vx / q
                sumvz += 1.0 / q
    else:
        for i in range(res - 1):
            vx = (drow[i + 1] - drow[i]) / dx
            q = _safe_exp(vx * vx / sigma2)
            sumvx += vx / q
            sumvz += 1.0 / q

    # C computes: return sumvx/sumvz * dx  →  (sumvx/sumvz) * dx
    return (sumvx / sumvz) * dx


def _safe_exp(value: float) -> float:
    """Return ``exp(value)`` matching C's `exp()` which returns ``HUGE_VAL``
    (infinity) on overflow without raising an error."""
    try:
        return math.exp(value)
    except OverflowError:
        return math.inf


def _untilt_row(drow: np.ndarray, res: int, bx: float) -> None:
    """Subtract the fitted facet tilt from a row (in-place).

    The C implementation checks ``if (!bx)`` before applying; a NaN
    ``bx`` is truthy in IEEE semantics, so the subtraction proceeds,
    producing NaN output from the row pivot.

    Parameters
    ----------
    drow : 1-D mutable float64 array.
    res : int
        Number of columns (xres).
    bx : float
        Estimated tilt (a slope * dx product).  When 0.0, the row is
        not modified.
    """
    if bx == 0.0:
        return

    half = 0.5 * (res - 1)
    for i in range(res):
        x = i - half
        drow[i] -= bx * x


def _mincount(xres: int) -> int:
    """Reproduce ``GWY_ROUND(log(xres) + 1)``, i.e. ``floor(x + 0.5)``."""
    return math.floor(math.log(xres) + 1.0 + 0.5)


def oracle_facet_tilt(
    data: np.ndarray,
    mask: np.ndarray | None,
    masking_mode: Literal["include", "exclude", "ignore"],
    dx: float,
    direction: Literal["horizontal", "vertical"],
    extract_background: bool,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray]:
    """Independent Python oracle for Gwyddion 2.71 linematch_do_facet_tilt.

    Parameters
    ----------
    data : (yres, xres) float64 array.
        Input height field; is *not* mutated (a working copy is made).
    mask : None or same-shape float64 array.
        Per-pixel data-quality weights with per-row C mask predicates.
    masking_mode : str
        ``"include"`` (mask >= 1.0 for both pixels), ``"exclude"``
        (mask <= 0.0 for both pixels), or ``"ignore"`` (mask unused).
    dx : float
        Physical pixel spacing in data units (xreal / xres).
    direction : str
        ``"horizontal"`` or ``"vertical"``.  For vertical processing
        the field is transposed before the loop and restored afterwards,
        matching the Gwyddion execute() transpose/reverse logic.
    extract_background : bool
        When True, the returned background array is the elementwise
        ``input - corrected`` computed in row-major C order.

    Returns
    -------
    corrected : float64 (yres, xres) array.
        The facet-tilt-corrected field.
    background : float64 (yres, xres) or None.
        ``input - corrected``, computed row-major in C operation order,
        or None when ``extract_background`` is False.
    shifts : float64 array.
        All zeros; the Gwyddion source calls ``gwy_data_line_clear``
        after processing.  The length equals the working field's
        y-resolution (original yres for horizontal, original xres for
        vertical).
    """
    yres, xres = data.shape

    if direction == "vertical":
        # After transpose, xres and yres swap roles.
        working = np.ascontiguousarray(data.T, dtype=np.float64)
        working_mask = (
            None
            if mask is None
            else np.ascontiguousarray(mask.T, dtype=np.float64)
        )
        work_yres, work_xres = working.shape
    else:
        working = np.ascontiguousarray(data.copy(), dtype=np.float64)
        working_mask = mask
        work_yres, work_xres = yres, xres

    mincount_val = _mincount(work_xres)

    for row_idx in range(work_yres):
        drow = working[row_idx]
        mrow = working_mask[row_idx] if working_mask is not None else None
        for _ in range(30):
            tilt = _row_fit_facet_tilt(
                drow, mrow, masking_mode, dx, mincount_val
            )
            _untilt_row(drow, work_xres, tilt)
            if math.fabs(tilt / dx) < 1e-6:
                break

    corrected = (
        np.ascontiguousarray(working.T) if direction == "vertical" else working
    )

    if extract_background:
        background = np.empty_like(data, order="C")
        for row in range(data.shape[0]):
            for col in range(data.shape[1]):
                background[row, col] = data[row, col] - corrected[row, col]
    else:
        background = None

    shifts = np.zeros(work_yres, dtype=np.float64, order="C")
    return corrected, background, shifts
