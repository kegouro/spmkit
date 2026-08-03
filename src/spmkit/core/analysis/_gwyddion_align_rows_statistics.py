"""Private portable Gwyddion 2.71 Align Rows statistics kernel.

This module intentionally implements only the four source-confirmed row-shift
statistics methods.  It is not a public API and does not emulate the installed
package's compiler-specific reassociation profile.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import cast

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


class _GwyddionAlignRowsMethod(IntEnum):
    """The four source-confirmed Align Rows row-shift methods."""

    MEDIAN = 1
    MEDIAN_OF_DIFFERENCES = 2
    TRIMMED_MEAN = 5
    TRIMMED_MEAN_OF_DIFFERENCES = 6


class _GwyddionMaskMode(IntEnum):
    """Gwyddion's stored mask enum, including its source value order."""

    EXCLUDE = 0
    INCLUDE = 1
    IGNORE = 2


class _GwyddionAlignRowsDirection(IntEnum):
    """Source row orientation before optional transpose/restore."""

    HORIZONTAL = 0
    VERTICAL = 1


@dataclass(frozen=True)
class _GwyddionAlignRowsStatisticsResult:
    """Corrected private result with optional extracted background diagnostics."""

    corrected: FloatArray
    background: FloatArray | None
    correction_sequence: FloatArray


def _validated_field(value: ArrayLike, *, label: str) -> FloatArray:
    try:
        source = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"Gwyddion Align Rows {label} must be array-compatible") from exc
    if source.ndim != 2:
        raise ValueError(f"Gwyddion Align Rows {label} must be two-dimensional")
    if 0 in source.shape:
        raise ValueError(f"Gwyddion Align Rows {label} must have non-empty dimensions")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError(f"Gwyddion Align Rows {label} must contain real numeric values")
    values = np.array(source, dtype=np.float64, order="C", copy=True)
    if not np.isfinite(values).all():
        raise ValueError(f"Gwyddion Align Rows {label} must be finite")
    return values


def _validated_mask(value: ArrayLike | None, shape: tuple[int, int]) -> FloatArray | None:
    if value is None:
        return None
    mask = _validated_field(value, label="mask")
    if mask.shape != shape:
        raise ValueError("Gwyddion Align Rows mask shape must match data")
    return mask


def _validated_enum(value: object, enum_type: type[IntEnum], label: str) -> IntEnum:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer, IntEnum)):
        raise TypeError(f"Gwyddion Align Rows {label} must be an integer enum value")
    try:
        return enum_type(int(value))
    except ValueError as exc:
        allowed = ", ".join(str(int(member)) for member in enum_type)
        raise ValueError(f"Gwyddion Align Rows {label} must be one of {allowed}") from exc


def _validated_trim_fraction(value: object) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        raise TypeError("Gwyddion Align Rows trim_fraction must be a real scalar")
    fraction = float(value)
    if not math.isfinite(fraction):
        raise ValueError("Gwyddion Align Rows trim_fraction must be finite")
    if not 0.0 <= fraction <= 0.5:
        raise ValueError(
            "Gwyddion Align Rows trim_fraction must be in the inclusive range 0.0..0.5"
        )
    return fraction


def _round_nonnegative(value: float) -> int:
    """Return the source's non-negative ``floor(x + 0.5)`` conversion."""
    return math.floor(value + 0.5)


def _mean_in_order(values: list[float]) -> float:
    if not values:
        raise ValueError("Gwyddion Align Rows mean requires samples")
    total = 0.0
    for value in values:
        total = total + value
    return total / len(values)


def _upper_median(values: list[float]) -> float:
    if not values:
        raise ValueError("Gwyddion Align Rows median requires samples")
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _move_min_to_front(values: list[float]) -> None:
    smallest = values[0]
    for index in range(1, len(values)):
        candidate = values[index]
        if candidate < smallest:
            values[index] = smallest
            smallest = candidate
            values[0] = smallest


def _move_max_to_back(values: list[float]) -> None:
    largest = values[-1]
    final = len(values) - 1
    for index in range(final):
        candidate = values[index]
        if candidate > largest:
            values[index] = largest
            largest = candidate
            values[final] = largest


def _trimmed_mean_or_median(values: list[float], trim_fraction: float) -> float:
    """Reduce selected samples in the frozen portable binary64 operation order."""
    count = len(values)
    if not count:
        raise ValueError("Gwyddion Align Rows reduction requires samples")
    trim_count = _round_nonnegative(trim_fraction * count)
    if 2 * trim_count + 1 >= count:
        return _upper_median(values)
    work = list(values)
    if trim_count == 0:
        return _mean_in_order(work)
    if trim_count == 1:
        if count % 2:
            _move_min_to_front(work)
            tail = work[1:]
            _move_max_to_back(tail)
            work[1:] = tail
        else:
            _move_max_to_back(work)
            head = work[:-1]
            _move_min_to_front(head)
            work[:-1] = head
        return _mean_in_order(work[1:-1])
    ordered = sorted(work)
    return _mean_in_order(ordered[trim_count : count - trim_count])


def _minimum_sample_count(width: int) -> int:
    return _round_nonnegative(math.log(width) + 1.0)


def _selected_row_values(
    row: FloatArray, mask_row: FloatArray | None, mode: _GwyddionMaskMode
) -> list[float]:
    if mask_row is None or mode is _GwyddionMaskMode.IGNORE:
        return [float(value) for value in row]
    if mode is _GwyddionMaskMode.INCLUDE:
        return [
            float(value)
            for value, mask_value in zip(row, mask_row, strict=True)
            if mask_value > 0.0
        ]
    return [
        float(value) for value, mask_value in zip(row, mask_row, strict=True) if mask_value < 1.0
    ]


def _selected_global_values(
    data: FloatArray, mask: FloatArray | None, mode: _GwyddionMaskMode
) -> list[float]:
    """Select the source-confirmed absolute-method fallback population.

    The global Exclude fallback uses ``mask <= 0`` rather than the per-row
    ``mask < 1`` predicate.  This source distinction is retained deliberately.
    """
    if mask is None or mode is _GwyddionMaskMode.IGNORE:
        return [float(value) for value in data.ravel(order="C")]
    values: list[float] = []
    for row, mask_row in zip(data, mask, strict=True):
        for value, mask_value in zip(row, mask_row, strict=True):
            if (
                mode is _GwyddionMaskMode.INCLUDE
                and mask_value > 0.0
                or mode is _GwyddionMaskMode.EXCLUDE
                and mask_value <= 0.0
            ):
                values.append(float(value))
    return values


def _paired_differences(
    data: FloatArray, mask: FloatArray | None, mode: _GwyddionMaskMode, row: int
) -> list[float]:
    first = data[row]
    second = data[row + 1]
    if mask is None or mode is _GwyddionMaskMode.IGNORE:
        return [float(second[column] - first[column]) for column in range(first.size)]
    first_mask = mask[row]
    second_mask = mask[row + 1]
    differences: list[float] = []
    for column in range(first.size):
        if mode is _GwyddionMaskMode.INCLUDE:
            keep = first_mask[column] > 1.0 and second_mask[column] > 1.0
        else:
            keep = first_mask[column] < 1.0 and second_mask[column] < 1.0
        if keep:
            differences.append(float(second[column] - first[column]))
    return differences


def _absolute_corrections(
    data: FloatArray, mask: FloatArray | None, mode: _GwyddionMaskMode, trim_fraction: float
) -> FloatArray:
    threshold = _minimum_sample_count(data.shape[1])
    global_values = _selected_global_values(data, mask, mode)
    fallback = _upper_median(global_values) if global_values else 0.0
    shifts: list[float] = []
    for row in range(data.shape[0]):
        selected = _selected_row_values(data[row], None if mask is None else mask[row], mode)
        shifts.append(
            _trimmed_mean_or_median(selected, trim_fraction)
            if len(selected) >= threshold
            else fallback
        )
    offset = _mean_in_order(shifts)
    return np.array([shift - offset for shift in shifts], dtype=np.float64, order="C")


def _slope_level(shifts: FloatArray) -> FloatArray:
    count = float(shifts.size)
    mean_index = (count - 1.0) / 2.0
    mean_index_square = (2.0 * count - 1.0) * (count - 1.0) / 6.0
    shift_values = [float(value) for value in shifts]
    mean_shifts = _mean_in_order(shift_values)
    index_weighted = 0.0
    for index, shift in enumerate(shift_values):
        index_weighted = index_weighted + shift * index
    index_weighted = index_weighted / count
    denominator = mean_index_square - mean_index * mean_index
    slope = (index_weighted - mean_shifts * mean_index) / denominator
    intercept = (mean_shifts * mean_index_square - mean_index * index_weighted) / denominator
    return np.array(
        [shift - (intercept + slope * index) for index, shift in enumerate(shift_values)],
        dtype=np.float64,
        order="C",
    )


def _difference_corrections(
    data: FloatArray, mask: FloatArray | None, mode: _GwyddionMaskMode, trim_fraction: float
) -> FloatArray:
    threshold = _minimum_sample_count(data.shape[1])
    shifts = np.zeros(data.shape[0], dtype=np.float64)
    for row in range(data.shape[0] - 1):
        selected = _paired_differences(data, mask, mode, row)
        shifts[row + 1] = (
            _trimmed_mean_or_median(selected, trim_fraction) if len(selected) >= threshold else 0.0
        )
    for row in range(1, shifts.size):
        shifts[row] = shifts[row] + shifts[row - 1]
    return _slope_level(shifts)


def _apply_corrections(data: FloatArray, corrections: FloatArray) -> FloatArray:
    corrected = data.copy(order="C")
    for row in range(corrected.shape[0]):
        for column in range(corrected.shape[1]):
            corrected[row, column] = corrected[row, column] - corrections[row]
    return corrected


def _background_in_order(input_data: FloatArray, corrected: FloatArray) -> FloatArray:
    background = np.empty_like(input_data, order="C")
    for row in range(input_data.shape[0]):
        for column in range(input_data.shape[1]):
            background[row, column] = input_data[row, column] - corrected[row, column]
    return background


def _gwyddion_align_rows_statistics_result(
    data: ArrayLike,
    *,
    method: object,
    masking_mode: object,
    direction: object,
    trim_fraction: object,
    mask: ArrayLike | None = None,
    extract_background: object = False,
) -> _GwyddionAlignRowsStatisticsResult:
    """Compute one private portable Align Rows statistics result without input mutation."""
    values = _validated_field(data, label="data")
    validated_mask = _validated_mask(mask, values.shape)
    selected_method = cast(
        _GwyddionAlignRowsMethod,
        _validated_enum(method, _GwyddionAlignRowsMethod, "method"),
    )
    selected_mode = cast(
        _GwyddionMaskMode,
        _validated_enum(masking_mode, _GwyddionMaskMode, "masking_mode"),
    )
    selected_direction = cast(
        _GwyddionAlignRowsDirection,
        _validated_enum(direction, _GwyddionAlignRowsDirection, "direction"),
    )
    fraction = _validated_trim_fraction(trim_fraction)
    if not isinstance(extract_background, (bool, np.bool_)):
        raise TypeError("Gwyddion Align Rows extract_background must be boolean")

    effective_mask = (
        None
        if validated_mask is None or selected_mode is _GwyddionMaskMode.IGNORE
        else validated_mask
    )
    if selected_direction is _GwyddionAlignRowsDirection.HORIZONTAL:
        working = values
        working_mask = effective_mask
    else:
        working = np.ascontiguousarray(values.T, dtype=np.float64)
        working_mask = (
            None
            if effective_mask is None
            else np.ascontiguousarray(effective_mask.T, dtype=np.float64)
        )

    if selected_method in (_GwyddionAlignRowsMethod.MEDIAN, _GwyddionAlignRowsMethod.TRIMMED_MEAN):
        reduction_fraction = 0.5 if selected_method is _GwyddionAlignRowsMethod.MEDIAN else fraction
        corrections = _absolute_corrections(
            working, working_mask, selected_mode, reduction_fraction
        )
    else:
        reduction_fraction = (
            0.5 if selected_method is _GwyddionAlignRowsMethod.MEDIAN_OF_DIFFERENCES else fraction
        )
        corrections = _difference_corrections(
            working, working_mask, selected_mode, reduction_fraction
        )

    corrected_working = _apply_corrections(working, corrections)
    corrected = (
        corrected_working
        if selected_direction is _GwyddionAlignRowsDirection.HORIZONTAL
        else np.ascontiguousarray(corrected_working.T)
    )
    background = _background_in_order(values, corrected) if extract_background else None
    return _GwyddionAlignRowsStatisticsResult(
        corrected=corrected, background=background, correction_sequence=corrections
    )
