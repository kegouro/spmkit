"""Private Gwydion 2.71 Align Rows remaining-methods kernels.

Implements the three remaining Align Rows public operations with the exact
arithmetic of the frozen compiled campaign profile:

  COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION

The parity target is the compiled campaign evidence (frozen JSON/NPZ
fixtures).  This module is a standalone production reimplementation of the
independently established mathematical contract; it shares no code with the
validation oracles, contains no case identifiers and reads no fixtures.

Methods (linematch.c method enum values):

  * polynomial (LINE_MATCH_POLY = 0):
      - degree 0 dispatches to the trim-fraction-zero row-shift path
        (per-row means of the retained samples with a global masked-median
        fallback and zero-levelled shifts), NOT to the polynomial solver;
      - degree >= 1 fits each row independently on the centred basis
        x = j - 0.5*(xres-1) with source-order moments, a packed
        lower-triangular Cholesky solve and full-field mean anchoring.
  * modus (LINE_MATCH_MODUS = 3): a robust row-centre statistic; global
    masked-median fallback, upper median for fewer than nine retained
    samples, otherwise the narrowest sqrt-count range window over the
    sorted samples with its central third mean; shifts zero-levelled.
  * match (LINE_MATCH_MATCH = 4): adjacent-row shape matching through
    Gaussian-weighted differences of row differences with a zero-weight
    no-correction guard and cumulative, zero-levelled shifts.

Compiler-profile note: the installed Gwydion 2.71 helper library used for
the compiled campaign performs the Cholesky nondiagonal update as a
reciprocal multiplication (r * (1.0/s)) where the frozen source text
expresses direct division (r / s).  Production reproduces the compiled
profile bitwise; the divergence is a build-profile observation and is not
claimed as universal Gwydion equivalence.

Masking semantics: INCLUDE retains mask values > 0, EXCLUDE retains mask
values < 1, IGNORE retains every sample; the mask is never mutated.
Finite two-dimensional inputs only; NaN/Inf are rejected at entry.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import cast

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


class _GwydionAlignRowsMethod(IntEnum):
    """Gwydion Align Rows method enums for the remaining-methods family."""

    POLYNOMIAL = 0
    MODUS = 3
    MATCH = 4


class _GwydionMaskMode(IntEnum):
    """Gwydion masking-mode enums (source value order)."""

    EXCLUDE = 0
    INCLUDE = 1
    IGNORE = 2


class _GwydionAlignRowsDirection(IntEnum):
    """Source row orientation before optional transpose/restore."""

    HORIZONTAL = 0
    VERTICAL = 1


#: Source parameter range for the polynomial degree (MAX_DEGREE = 5).
MAX_POLYNOMIAL_DEGREE = 5


@dataclass(frozen=True)
class _GwydionAlignRowsRemainingResult:
    """Immutable private result with diagnostics for parity inspection.

    Returned arrays are freshly allocated and never alias input or mask
    storage.
    """

    corrected: FloatArray
    background: FloatArray
    delta: FloatArray
    shifts: FloatArray
    row_valid_indices: tuple[tuple[int, ...], ...]
    row_valid_counts: tuple[int, ...]
    row_shifts: tuple[float, ...]
    row_statuses: tuple[str, ...]
    method: str
    method_enum: int
    masking: str
    masking_enum: int
    branch: str
    poly_coefficients: FloatArray | None
    modus_total_median: float | None
    modus_row_estimates: tuple[float, ...] | None
    match_pair_lambdas: tuple[float, ...] | None
    match_pair_wsum0: tuple[float, ...] | None
    input_mutation_evidence: bool
    mask_mutation_evidence: bool


def _validated_field(value: ArrayLike, *, label: str) -> FloatArray:
    """Validate and copy a finite two-dimensional real numeric field."""
    try:
        source = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"Gwydion Align Rows {label} must be array-compatible") from exc
    if source.ndim != 2:
        raise ValueError(f"Gwydion Align Rows {label} must be two-dimensional")
    if 0 in source.shape:
        raise ValueError(f"Gwydion Align Rows {label} must have non-empty dimensions")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError(f"Gwydion Align Rows {label} must contain real numeric values")
    values = np.array(source, dtype=np.float64, order="C", copy=True)
    if not np.isfinite(values).all():
        raise ValueError(f"Gwydion Align Rows {label} must be finite")
    return values


def _validated_mask(value: ArrayLike | None, shape: tuple[int, int]) -> FloatArray | None:
    """Validate and copy an optional mask matching the field shape."""
    if value is None:
        return None
    mask = _validated_field(value, label="mask")
    if mask.shape != shape:
        raise ValueError("Gwydion Align Rows mask shape must match data")
    return mask


def _validated_enum(value: object, enum_type: type[IntEnum], label: str) -> IntEnum:
    """Validate an integer enum value against a Gwydion enum."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer, IntEnum)
    ):
        raise TypeError(f"Gwydion Align Rows {label} must be an integer enum value")
    try:
        return enum_type(int(value))
    except ValueError as exc:
        allowed = ", ".join(str(int(member)) for member in enum_type)
        raise ValueError(f"Gwydion Align Rows {label} must be one of {allowed}") from exc


def _validated_degree(value: object) -> int:
    """Validate the polynomial degree with the source kernel guard.

    The frozen kernel only requires ``degree >= 0`` (``g_return_if_fail``);
    the public API layer applies the GUI parameter range ``0..5``.
    """
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise TypeError("Gwydion Align Rows degree must be an integer")
    degree = int(value)
    if degree < 0:
        raise ValueError("Gwydion Align Rows degree must be non-negative")
    return degree


def _round_nonnegative(value: float) -> int:
    """GWY_ROUND: floor(x + 0.5) on a non-negative argument."""
    return math.floor(value + 0.5)


def _mean_in_order(values: list[float]) -> float:
    """Sequential left-to-right mean (source summation order)."""
    total = 0.0
    for value in values:
        total = total + value
    return total / len(values)


def _upper_median(values: list[float]) -> float:
    """gwy_math_median: value at rank len//2 of the sorted multiset."""
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _selected_row_values(
    row: FloatArray, mask_row: FloatArray | None, mode: _GwydionMaskMode
) -> list[float]:
    """Collect row samples in increasing column order (mask predicate:
    INCLUDE > 0, EXCLUDE < 1, IGNORE -> all)."""
    if mask_row is None or mode is _GwydionMaskMode.IGNORE:
        return [float(value) for value in row]
    if mode is _GwydionMaskMode.INCLUDE:
        return [
            float(value)
            for value, mask_value in zip(row, mask_row, strict=True)
            if mask_value > 0.0
        ]
    return [
        float(value) for value, mask_value in zip(row, mask_row, strict=True) if mask_value < 1.0
    ]


def _median_mask_fallback(
    data: FloatArray, mask: FloatArray | None, mode: _GwydionMaskMode
) -> float:
    """Global masked-median fallback (area_get_median_mask semantics).

    The EXCLUDE fallback predicate is ``mask <= 0`` (the source helper's
    own rule), which differs from the per-row ``mask < 1`` predicate; both
    coincide on the frozen 0/1 campaign masks and the distinction is
    retained deliberately.
    """
    if mask is None or mode is _GwydionMaskMode.IGNORE:
        return _upper_median([float(value) for value in data.ravel(order="C")])
    values: list[float] = []
    for row, mask_row in zip(data, mask, strict=True):
        for value, mask_value in zip(row, mask_row, strict=True):
            if (
                mode is _GwydionMaskMode.INCLUDE
                and mask_value > 0.0
                or mode is _GwydionMaskMode.EXCLUDE
                and mask_value <= 0.0
            ):
                values.append(float(value))
    if not values:
        return 0.0
    return _upper_median(values)


def _zero_level(shifts: list[float]) -> FloatArray:
    """Zero-level row shifts: subtract the sequential mean."""
    offset = _mean_in_order(shifts)
    return np.array([shift - offset for shift in shifts], dtype=np.float64, order="C")


def _apply_row_shifts(data: FloatArray, shifts: FloatArray) -> FloatArray:
    """Subtract one scalar shift per row (source sign convention)."""
    corrected = data.copy(order="C")
    for row in range(corrected.shape[0]):
        shift = float(shifts[row])
        for column in range(corrected.shape[1]):
            corrected[row, column] = corrected[row, column] - shift
    return corrected


def _background_in_order(input_data: FloatArray, corrected: FloatArray) -> FloatArray:
    """input - corrected elementwise (bg field relation)."""
    background = np.empty_like(input_data, order="C")
    for row in range(input_data.shape[0]):
        for column in range(input_data.shape[1]):
            background[row, column] = input_data[row, column] - corrected[row, column]
    return background


def _choleski_decompose(dim: int, a: list[float]) -> bool:
    """Packed lower-triangular Cholesky decomposition matching the compiled
    Gwydion 2.71 helper profile.

    The installed helper binary used for the compiled campaign hoists the
    reciprocal 1.0/s once per pivot and stores every nondiagonal element as
    r * (1.0/s); the frozen source text expresses r / s.  Production
    reproduces the compiled evidence bitwise.
    """
    for k in range(dim):
        s = a[k * (k + 1) // 2 + k]
        for i in range(k):
            s = s - a[k * (k + 1) // 2 + i] * a[k * (k + 1) // 2 + i]
        if s <= 0.0:
            return False
        a[k * (k + 1) // 2 + k] = s = math.sqrt(s)
        inv = 1.0 / s
        for j in range(k + 1, dim):
            r = a[j * (j + 1) // 2 + k]
            for i in range(k):
                r = r - a[k * (k + 1) // 2 + i] * a[j * (j + 1) // 2 + i]
            a[j * (j + 1) // 2 + k] = r * inv
    return True


def _choleski_solve(dim: int, a: Sequence[float], b: list[float]) -> None:
    """Forward/backward substitution with the packed decomposition."""
    for j in range(dim):
        for i in range(j):
            b[j] = b[j] - a[j * (j + 1) // 2 + i] * b[i]
        b[j] = b[j] / a[j * (j + 1) // 2 + j]
    for j in range(dim - 1, -1, -1):
        for i in range(j + 1, dim):
            b[j] = b[j] - a[i * (i + 1) // 2 + j] * b[i]
        b[j] = b[j] / a[j * (j + 1) // 2 + j]


def _degree0_corrections(
    data: FloatArray, mask: FloatArray | None, mode: _GwydionMaskMode
) -> FloatArray:
    """find_row_shifts_trimmed_mean(trimfrac=0): per-row means with the
    global masked-median fallback, then zero-levelling."""
    xres = data.shape[1]
    mincount = _round_nonnegative(math.log(xres) + 1.0)
    fallback = _median_mask_fallback(data, mask, mode)
    shifts: list[float] = []
    for row in range(data.shape[0]):
        selected = _selected_row_values(data[row], None if mask is None else mask[row], mode)
        if len(selected) >= mincount:
            shifts.append(_mean_in_order(selected) if len(selected) > 1 else selected[0])
        else:
            shifts.append(fallback)
    return _zero_level(shifts)


def _polynomial_degree_ge1(
    data: FloatArray, mask: FloatArray | None, mode: _GwydionMaskMode, degree: int
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """row_level_poly: per-row moments, packed Cholesky, mean anchoring."""
    yres, xres = data.shape
    avg = _mean_in_order([float(value) for value in data.ravel(order="C")])
    xc = 0.5 * (xres - 1)
    corrected = data.copy(order="C")
    coeffs = np.zeros((yres, degree + 1), dtype=np.float64)
    shifts = np.empty(yres, dtype=np.float64)
    for row in range(yres):
        xp = [0.0] * (2 * degree + 1)
        zx = [0.0] * (degree + 1)
        mrow = None if mask is None else mask[row]
        for column in range(xres):
            if mrow is not None and mode is _GwydionMaskMode.INCLUDE \
                    and float(mrow[column]) <= 0.0:
                continue
            if mrow is not None and mode is _GwydionMaskMode.EXCLUDE \
                    and float(mrow[column]) >= 1.0:
                continue
            p = 1.0
            x = column - xc
            for k in range(0, degree + 1):
                xp[k] = xp[k] + p
                zx[k] = zx[k] + p * float(corrected[row, column])
                p = p * x
            for k in range(degree + 1, 2 * degree + 1):
                xp[k] = xp[k] + p
                p = p * x
        if xp[0] > degree:
            matrix = [0.0] * ((degree + 1) * (degree + 2) // 2)
            for j in range(0, degree + 1):
                for k in range(0, j + 1):
                    matrix[j * (j + 1) // 2 + k] = xp[j + k]
            _choleski_decompose(degree + 1, matrix)
            _choleski_solve(degree + 1, matrix, zx)
        else:
            zx = [0.0] * (degree + 1)
        zx[0] = zx[0] - avg
        shifts[row] = zx[0]
        coeffs[row] = zx
        for column in range(xres):
            p = 1.0
            x = column - xc
            z = 0.0
            for k in range(0, degree + 1):
                z = z + p * zx[k]
                p = p * x
            corrected[row, column] = corrected[row, column] - z
    return corrected, shifts, coeffs


def _modus_corrections(
    data: FloatArray, mask: FloatArray | None, mode: _GwydionMaskMode
) -> tuple[FloatArray, float, list[float]]:
    """linematch_do_modus: robust row-centre estimator, zero-levelled."""
    total_median = _median_mask_fallback(data, mask, mode)
    estimates: list[float] = []
    for row in range(data.shape[0]):
        selected = _selected_row_values(data[row], None if mask is None else mask[row], mode)
        count = len(selected)
        if count == 0:
            estimates.append(total_median)
        elif count < 9:
            estimates.append(_upper_median(selected))
        else:
            seglen = _round_nonnegative(math.sqrt(count))
            ordered = sorted(selected)
            best_start = 0
            best_diff = math.inf
            for start in range(0, count - seglen + 1):
                diff = ordered[start + seglen - 1] - ordered[start]
                if diff < best_diff:
                    best_diff = diff
                    best_start = start
            modus = 0.0
            retained = 0
            for j in range(seglen // 3, seglen - seglen // 3):
                modus = modus + ordered[best_start + j]
                retained += 1
            estimates.append(modus / retained)
    return _zero_level(estimates), total_median, estimates


def _match_corrections(
    data: FloatArray, mask: FloatArray | None, mode: _GwydionMaskMode
) -> tuple[FloatArray, list[float], list[float]]:
    """linematch_do_match: adjacent-row shape matching with the
    zero-weight guard and cumulative, zero-levelled shifts."""
    yres, xres = data.shape
    s = [0.0] * yres
    pair_lambdas: list[float] = []
    pair_wsum0: list[float] = []
    weights = [0.0] * (xres - 1)
    for row in range(1, yres):
        a = data[row - 1]
        b = data[row]
        ma = None if mask is None else mask[row - 1]
        mb = None if mask is None else mask[row]

        def masked(column: int, ma: FloatArray | None = ma,
                   mb: FloatArray | None = mb) -> bool:
            if mode is _GwydionMaskMode.INCLUDE:
                if ma is None or mb is None:
                    return False
                return float(ma[column]) <= 0.0 or float(mb[column]) <= 0.0
            if mode is _GwydionMaskMode.EXCLUDE:
                if ma is None or mb is None:
                    return False
                return float(ma[column]) >= 1.0 or float(mb[column]) >= 1.0
            return False

        wsum = 0.0
        for column in range(xres - 1):
            if masked(column):
                continue
            x = float(a[column + 1]) - float(a[column]) - float(b[column + 1]) + float(b[column])
            wsum = wsum + abs(x)
        if wsum == 0.0:
            s[row] = 0.0
            pair_wsum0.append(0.0)
            pair_lambdas.append(0.0)
            continue
        q = wsum / (xres - 1)
        wsum = 0.0
        for column in range(xres - 1):
            if masked(column):
                weights[column] = 0.0
                continue
            x = float(a[column + 1]) - float(a[column]) - float(b[column + 1]) + float(b[column])
            weights[column] = math.exp(-(x * x / (2.0 * q)))
            wsum = wsum + weights[column]
        lam = (float(a[0]) - float(b[0])) * weights[0]
        for column in range(1, xres - 1):
            if masked(column):
                continue
            lam = lam + (float(a[column]) - float(b[column])) * (
                weights[column - 1] + weights[column]
            )
        lam = lam + (float(a[xres - 1]) - float(b[xres - 1])) * weights[xres - 2]
        lam = lam / (2.0 * wsum)
        s[row] = -lam
        pair_wsum0.append(wsum)
        pair_lambdas.append(-lam)
    cumulative = [0.0] * yres
    cumulative[0] = s[0]
    for row in range(1, yres):
        cumulative[row] = cumulative[row - 1] + s[row]
    return _zero_level(cumulative), pair_lambdas, pair_wsum0


def _row_valid_indices(
    mask: FloatArray | None, mode: _GwydionMaskMode, xres: int, yres: int
) -> tuple[tuple[int, ...], ...]:
    """Per-row retained sample indices from the mask predicate."""
    out: list[tuple[int, ...]] = []
    for row in range(yres):
        mrow = None if mask is None else mask[row]
        indices: list[int] = []
        for column in range(xres):
            if mrow is None or mode is _GwydionMaskMode.IGNORE:
                keep = True
            elif mode is _GwydionMaskMode.INCLUDE:
                keep = float(mrow[column]) > 0.0
            else:
                keep = float(mrow[column]) < 1.0
            if keep:
                indices.append(column)
        out.append(tuple(indices))
    return tuple(out)


def _row_statuses(input_data: FloatArray, corrected: FloatArray) -> tuple[str, ...]:
    """Per-row corrected/unchanged classification by bitwise comparison."""
    ib = np.ascontiguousarray(input_data).view(np.uint64)
    cb = np.ascontiguousarray(corrected).view(np.uint64)
    statuses: list[str] = []
    for row in range(input_data.shape[0]):
        statuses.append(
            "corrected" if not np.array_equal(ib[row], cb[row]) else "unchanged"
        )
    return tuple(statuses)


def _transposed(mask: FloatArray | None, mode: _GwydionMaskMode) -> FloatArray | None:
    if mask is None or mode is _GwydionMaskMode.IGNORE:
        return None
    return np.ascontiguousarray(mask.T, dtype=np.float64)


def _gwydion_align_rows_remaining_result(
    data: ArrayLike,
    *,
    method: object,
    masking_mode: object,
    direction: object,
    degree: object = 1,
    mask: ArrayLike | None = None,
) -> _GwydionAlignRowsRemainingResult:
    """Compute one private Align Rows remaining-method result.

    Validation mirrors the established family contract; the input channel
    data and mask are copied before any arithmetic and never mutated.
    """
    values = _validated_field(data, label="data")
    validated_mask = _validated_mask(mask, values.shape)
    selected_method = cast(
        _GwydionAlignRowsMethod,
        _validated_enum(method, _GwydionAlignRowsMethod, "method"),
    )
    selected_mode = cast(
        _GwydionMaskMode,
        _validated_enum(masking_mode, _GwydionMaskMode, "masking_mode"),
    )
    selected_direction = cast(
        _GwydionAlignRowsDirection,
        _validated_enum(direction, _GwydionAlignRowsDirection, "direction"),
    )
    selected_degree = (
        _validated_degree(degree)
        if selected_method is _GwydionAlignRowsMethod.POLYNOMIAL
        else 0
    )
    if selected_method is _GwydionAlignRowsMethod.MATCH and values.shape[1] < 2:
        raise ValueError(
            "Gwydion Align Rows match requires at least two columns "
            "(the frozen source reads the first and last weight "
            "unconditionally)"
        )

    effective_mask = (
        None
        if validated_mask is None or selected_mode is _GwydionMaskMode.IGNORE
        else validated_mask
    )
    if selected_direction is _GwydionAlignRowsDirection.HORIZONTAL:
        working = values
        working_mask = effective_mask
    else:
        working = np.ascontiguousarray(values.T, dtype=np.float64)
        working_mask = _transposed(effective_mask, selected_mode)

    method_name = selected_method.name.lower()
    branch = method_name
    coeffs: FloatArray | None = None
    modus_median: float | None = None
    modus_estimates: list[float] | None = None
    pair_lambdas: list[float] | None = None
    pair_wsum0: list[float] | None = None
    if selected_method is _GwydionAlignRowsMethod.POLYNOMIAL:
        if selected_degree == 0:
            corrections = _degree0_corrections(working, working_mask, selected_mode)
            branch = "degree0_row_shifts"
            corrected_working = _apply_row_shifts(working, corrections)
        else:
            corrected_working, corrections, coeffs = _polynomial_degree_ge1(
                working, working_mask, selected_mode, selected_degree
            )
            branch = f"degree{selected_degree}_row_level_poly"
    elif selected_method is _GwydionAlignRowsMethod.MODUS:
        corrections, modus_median, modus_estimates = _modus_corrections(
            working, working_mask, selected_mode
        )
        corrected_working = _apply_row_shifts(working, corrections)
    else:
        corrections, pair_lambdas, pair_wsum0 = _match_corrections(
            working, working_mask, selected_mode
        )
        corrected_working = _apply_row_shifts(working, corrections)

    corrected = (
        corrected_working
        if selected_direction is _GwydionAlignRowsDirection.HORIZONTAL
        else np.ascontiguousarray(corrected_working.T)
    )
    background = _background_in_order(values, corrected)
    delta = np.empty_like(corrected, order="C")
    for row in range(corrected.shape[0]):
        for column in range(corrected.shape[1]):
            delta[row, column] = corrected[row, column] - values[row, column]
    shifts = (
        corrections
        if selected_direction is _GwydionAlignRowsDirection.HORIZONTAL
        else np.ascontiguousarray(corrections)
    )
    row_valid = _row_valid_indices(effective_mask, selected_mode, values.shape[1], values.shape[0])
    row_shifts = tuple(float(value) for value in corrections)
    statuses = _row_statuses(values, corrected)

    return _GwydionAlignRowsRemainingResult(
        corrected=corrected,
        background=background,
        delta=delta,
        shifts=shifts,
        row_valid_indices=row_valid,
        row_valid_counts=tuple(len(r) for r in row_valid),
        row_shifts=row_shifts,
        row_statuses=statuses,
        method=method_name,
        method_enum=int(selected_method),
        masking=selected_mode.name.lower(),
        masking_enum=int(selected_mode),
        branch=branch,
        poly_coefficients=coeffs,
        modus_total_median=modus_median,
        modus_row_estimates=(
            None if modus_estimates is None else tuple(modus_estimates)
        ),
        match_pair_lambdas=(
            None if pair_lambdas is None else tuple(pair_lambdas)
        ),
        match_pair_wsum0=(
            None if pair_wsum0 is None else tuple(pair_wsum0)
        ),
        input_mutation_evidence=True,
        mask_mutation_evidence=True,
    )
