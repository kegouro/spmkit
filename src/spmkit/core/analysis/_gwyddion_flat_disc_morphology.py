"""Diagnostic model of the Gwyddion min/max RLE reduction hierarchy.

This is an executable-evidence model, not an oracle.  It preserves the
precomputed ``Each``/``Even`` construction and every comparison site.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

Kind = Literal["each", "even"]


@dataclass(frozen=True)
class _GwyddionFlatDiscKernelSpec:
    size_px: int
    kernel_resolution: int
    kernel_active_count: int


@dataclass(frozen=True)
class _GwyddionFlatDiscMorphologyResult:
    opening: NDArray[np.float64]
    closing: NDArray[np.float64]
    kernel: _GwyddionFlatDiscKernelSpec


def _validated_gwyddion_flat_disc_size(size_px: object) -> int:
    if isinstance(size_px, (bool, np.bool_)) or not isinstance(size_px, (int, np.integer)):
        raise TypeError("size_px must be a Python or NumPy integer scalar; booleans are invalid")
    value = int(size_px)
    if not 2 <= value <= 31:
        raise ValueError("size_px must be in the inclusive range 2..31")
    return value


def _validated_gwyddion_flat_disc_data(data: ArrayLike) -> NDArray[np.float64]:
    field = np.asarray(data, dtype=np.float64)
    if field.ndim != 2:
        raise ValueError("data must be exactly two-dimensional")
    if 0 in field.shape:
        raise ValueError("data dimensions must be non-empty")
    if not np.isfinite(field).all():
        raise ValueError("data values must all be finite")
    return np.array(field, dtype=np.float64, order="C", copy=True)


@dataclass
class Requirement:
    needed: bool = False
    even_even: bool = False
    even_odd: bool = False
    sublen1: int = 0
    sublen2: int = 0


@dataclass
class Plan:
    each: dict[int, Requirement] = field(default_factory=dict)
    even: dict[int, Requirement] = field(default_factory=dict)

    def requirement(self, kind: Kind, length: int) -> Requirement:
        mapping = self.even if kind == "even" else self.each
        return mapping.setdefault(length, Requirement())


def _set_requirement(
    plan: Plan,
    kind: Kind,
    length: int,
    sublen1: int,
    sublen2: int,
    even_odd: bool,
    even_even: bool,
) -> None:
    item = plan.requirement(kind, length)
    item.sublen1 = sublen1
    item.sublen2 = sublen2
    item.even_odd = even_odd
    item.even_even = even_even


def _need(plan: Plan, kind: Kind, length: int) -> bool:
    item = plan.requirement(kind, length)
    if item.needed:
        return True
    item.needed = True
    return False


def _build_requirement(plan: Plan, length: int, even: bool) -> None:
    kind: Kind = "even" if even else "each"
    if _need(plan, kind, length):
        return
    if even:
        if length == 2:
            _set_requirement(plan, kind, length, 1, 1, False, False)
            _build_requirement(plan, 1, False)
        elif length % 4 == 0:
            _set_requirement(plan, kind, length, length // 2, length // 2, False, True)
            _build_requirement(plan, length // 2, True)
        else:
            _set_requirement(plan, kind, length, length // 2 - 1, length // 2 + 1, False, True)
            _build_requirement(plan, length // 2 - 1, True)
            _build_requirement(plan, length // 2 + 1, True)
        return
    if length == 1:
        return
    if length % 2 == 0:
        for left in range(1, length // 2 + 1):
            right = length - left
            if plan.requirement("each", left).needed and plan.requirement("each", right).needed:
                _set_requirement(plan, kind, length, left, right, False, False)
                return
        _set_requirement(plan, kind, length, length // 2, length // 2, False, False)
        _build_requirement(plan, length // 2, False)
        return
    possible = 0
    for left in range(1, length // 2 + 1):
        right = length - left
        if plan.requirement("each", left).needed and plan.requirement("each", right).needed:
            _set_requirement(plan, kind, length, left, right, False, False)
            return
        if plan.requirement("even", left).needed and plan.requirement("each", right).needed:
            _set_requirement(plan, kind, length, left, right, True, False)
            return
        if plan.requirement("each", left).needed and plan.requirement("even", right).needed:
            _set_requirement(plan, kind, length, right, left, True, False)
            return
        if plan.requirement("each", left).needed:
            possible = left
    if possible:
        _set_requirement(plan, kind, length, possible, length - possible, False, False)
        _build_requirement(plan, length - possible, False)
    elif length % 4 == 1:
        _set_requirement(plan, kind, length, length // 2, length // 2 + 1, True, False)
        _build_requirement(plan, length // 2, True)
        _build_requirement(plan, length // 2 + 1, False)
    else:
        _set_requirement(plan, kind, length, length // 2 + 1, length // 2, True, False)
        _build_requirement(plan, length // 2 + 1, True)
        _build_requirement(plan, length // 2, False)


def _second_on_equal(left: np.uint64, right: np.uint64, maximum: bool) -> np.uint64:
    left_float = left.view(np.float64)
    right_float = right.view(np.float64)
    if maximum:
        return right if right_float >= left_float else left
    return right if right_float <= left_float else left


def _first_on_equal(left: np.uint64, right: np.uint64, maximum: bool) -> np.uint64:
    left_float = left.view(np.float64)
    right_float = right.view(np.float64)
    if maximum:
        return right if right_float > left_float else left
    return right if right_float < left_float else left


def _compose_each(left: np.ndarray, right: np.ndarray, a: int, b: int, maximum: bool) -> np.ndarray:
    target = np.zeros_like(left)
    for index in range(left.size - (a + b) + 1):
        target[index] = _second_on_equal(left[index], right[index + a], maximum)
    return target


def _compose_even(left: np.ndarray, right: np.ndarray, a: int, b: int, maximum: bool) -> np.ndarray:
    target = np.zeros_like(left)
    for index in range(0, left.size - (a + b) + 1, 2):
        target[index] = _second_on_equal(left[index], right[index + a], maximum)
    return target


def _compose_even_odd(
    even: np.ndarray, odd: np.ndarray, even_len: int, odd_len: int, maximum: bool
) -> np.ndarray:
    target = np.zeros_like(odd)
    count = odd.size - (even_len + odd_len)
    even_one, odd_one = 0, even_len
    even_two, odd_two = odd_len + 1, 1
    index = 0
    while index + 1 <= count:
        target[index] = _second_on_equal(even[even_one], odd[odd_one], maximum)
        index += 1
        even_one += 2
        odd_one += 2
        target[index] = _second_on_equal(even[even_two], odd[odd_two], maximum)
        index += 1
        even_two += 2
        odd_two += 2
    if index <= count:
        target[index] = _second_on_equal(even[even_one], odd[odd_one], maximum)
        index += 1
    if index <= count:
        target[index] = _second_on_equal(even[even_two], odd[odd_two], maximum)
    return target


def _row_precomputations(
    values: np.ndarray, lengths: tuple[int, ...], maximum: bool
) -> dict[int, np.ndarray]:
    plan = Plan()
    for length in sorted(set(lengths)):
        _build_requirement(plan, length, False)
    each: dict[int, np.ndarray] = {1: values.copy()}
    even: dict[int, np.ndarray] = {}
    max_each = max(plan.each, default=1)
    max_even = max(plan.even, default=0)
    for length in range(2, max_each + 1):
        requirement = plan.requirement("each", length)
        if requirement.needed:
            if requirement.even_odd:
                each[length] = _compose_even_odd(
                    even[requirement.sublen1],
                    each[requirement.sublen2],
                    requirement.sublen1,
                    requirement.sublen2,
                    maximum,
                )
            else:
                each[length] = _compose_each(
                    each[requirement.sublen1],
                    each[requirement.sublen2],
                    requirement.sublen1,
                    requirement.sublen2,
                    maximum,
                )
        if length <= max_even:
            requirement = plan.requirement("even", length)
            if requirement.needed:
                if requirement.even_even:
                    even[length] = _compose_even(
                        even[requirement.sublen1],
                        even[requirement.sublen2],
                        requirement.sublen1,
                        requirement.sublen2,
                        maximum,
                    )
                else:
                    even[length] = _compose_even(each[1], each[1], 1, 1, maximum)
    return each


@lru_cache(maxsize=30)
def _mask(size_px: int) -> np.ndarray:
    mask = np.zeros((size_px, size_px), dtype=np.uint8)
    half = size_px / 2.0
    for row in range(size_px):
        factor = ((row + 0.5) / half) * (2.0 - ((row + 0.5) / half))
        if factor > 0.0:
            first = max(0, int(np.ceil(half * (1.0 - np.sqrt(factor)) - 0.5)))
            last = min(size_px - 1, int(np.floor(half * (1.0 + np.sqrt(factor)) - 0.5)))
            mask[row, first : last + 1] = 1
    return mask


def _segments(size_px: int, maximum: bool) -> tuple[tuple[int, int, int], ...]:
    mask = _mask(size_px)
    if maximum:
        mask = mask[::-1, ::-1]
    result = []
    for row in range(size_px):
        columns = np.flatnonzero(mask[row])
        if columns.size:
            result.append((row, int(columns[0]), int(columns.size)))
    return tuple(result)


def filter_field(field: np.ndarray, size_px: int, maximum: bool) -> np.ndarray:
    field = np.ascontiguousarray(field, dtype=np.float64)
    rows, columns = field.shape
    segments = _segments(size_px, maximum)
    lengths = tuple(segment[2] for segment in segments)
    up = size_px // 2 if maximum else (size_px - 1) // 2
    left = size_px // 2 if maximum else (size_px - 1) // 2
    right = size_px - 1 - left
    result = np.empty(field.shape, dtype=np.uint64)
    field_bits = field.view(np.uint64)
    for output_row in range(rows):
        per_row = []
        for kernel_row in range(size_px):
            source_row = min(max(output_row + kernel_row - up, 0), rows - 1)
            extended = np.concatenate(
                (
                    np.repeat(field_bits[source_row, 0], left),
                    field_bits[source_row],
                    np.repeat(field_bits[source_row, -1], right),
                )
            )
            per_row.append(_row_precomputations(extended, lengths, maximum))
        for output_column in range(columns):
            value: np.uint64 | None = None
            for kernel_row, kernel_column, length in segments:
                candidate = per_row[kernel_row][length][output_column + kernel_column]
                value = candidate if value is None else _first_on_equal(value, candidate, maximum)
            assert value is not None
            result[output_row, output_column] = value
    return result.view(np.float64)


def opening(field: np.ndarray, size_px: int) -> np.ndarray:
    return filter_field(filter_field(field, size_px, False), size_px, True)


def closing(field: np.ndarray, size_px: int) -> np.ndarray:
    return filter_field(filter_field(field, size_px, True), size_px, False)


def _gwyddion_flat_disc_kernel(size_px: object) -> _GwyddionFlatDiscKernelSpec:
    value = _validated_gwyddion_flat_disc_size(size_px)
    return _GwyddionFlatDiscKernelSpec(
        size_px=value,
        kernel_resolution=value,
        kernel_active_count=int(_mask(value).sum()),
    )


def _gwyddion_flat_disc_extremum(
    data: ArrayLike,
    size_px: object,
    *,
    maximum: bool,
) -> NDArray[np.float64]:
    field = _validated_gwyddion_flat_disc_data(data)
    value = _validated_gwyddion_flat_disc_size(size_px)
    return np.array(filter_field(field, value, maximum), dtype=np.float64, order="C")


def _gwyddion_flat_disc_morphology_result(
    data: ArrayLike,
    size_px: object,
) -> _GwyddionFlatDiscMorphologyResult:
    field = _validated_gwyddion_flat_disc_data(data)
    kernel = _gwyddion_flat_disc_kernel(size_px)
    opening = np.array(
        filter_field(filter_field(field, kernel.size_px, False), kernel.size_px, True),
        dtype=np.float64,
        order="C",
    )
    closing = np.array(
        filter_field(filter_field(field, kernel.size_px, True), kernel.size_px, False),
        dtype=np.float64,
        order="C",
    )
    return _GwyddionFlatDiscMorphologyResult(
        opening=opening,
        closing=closing,
        kernel=kernel,
    )
