"""Private numerical kernel for the frozen Gwyddion 2.71 Path Level domain."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
_NormalizedLine = tuple[int, int, int, int]


@dataclass(frozen=True)
class _GwyddionPathLevelLine:
    """One ordered straight selection line in physical field coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class _GwyddionPathLevelResult:
    """Independent Path Level output and source-visible numerical diagnostics."""

    corrected: FloatArray
    normalized_lines: tuple[_NormalizedLine, ...]
    row_differences: FloatArray
    cumulative_row_correction: FloatArray
    thickness_px: int


def _validated_gwyddion_path_level_data(data: ArrayLike) -> FloatArray:
    """Return a finite, non-empty C-contiguous float64 copy of a field."""
    try:
        source = np.asarray(data)
    except (TypeError, ValueError) as exc:
        raise TypeError("Gwyddion Path Level requires array-compatible data") from exc
    if source.ndim != 2:
        raise ValueError("Gwyddion Path Level requires two-dimensional data")
    if 0 in source.shape:
        raise ValueError("Gwyddion Path Level requires non-empty dimensions")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError("Gwyddion Path Level requires real numeric data")
    values = np.array(source, dtype=np.float64, order="C", copy=True)
    if not np.isfinite(values).all():
        raise ValueError("Gwyddion Path Level requires finite data")
    return values


def _validated_gwyddion_path_level_lines(
    lines: object,
) -> tuple[_GwyddionPathLevelLine, ...]:
    """Validate an ordered, duplicate-preserving sequence of physical lines."""
    if isinstance(lines, (str, bytes)):
        raise TypeError("Gwyddion Path Level lines must be numeric coordinate rows")
    try:
        source = np.asarray(lines)
    except (TypeError, ValueError) as exc:
        raise TypeError("Gwyddion Path Level lines must be array-compatible") from exc
    if source.size == 0:
        if source.ndim not in (1, 2):
            raise ValueError("empty Gwyddion Path Level lines must be one- or two-dimensional")
        return ()
    if source.ndim != 2 or source.shape[1] != 4:
        raise ValueError("Gwyddion Path Level lines must have shape (n, 4)")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError("Gwyddion Path Level lines must contain real numeric coordinates")
    values = np.array(source, dtype=np.float64, order="C", copy=True)
    if not np.isfinite(values).all():
        raise ValueError("Gwyddion Path Level lines must be finite")
    return tuple(_GwyddionPathLevelLine(*(float(value) for value in row)) for row in values)


def _validated_gwyddion_path_level_thickness(thickness_px: object) -> int:
    """Validate the source-supported Path Level thickness range."""
    if isinstance(thickness_px, (bool, np.bool_)) or not isinstance(
        thickness_px, (int, np.integer)
    ):
        raise TypeError(
            "Gwyddion Path Level thickness_px must be a Python or NumPy integer scalar; "
            "booleans are invalid"
        )
    value = int(thickness_px)
    if not 1 <= value <= 128:
        raise ValueError("Gwyddion Path Level thickness_px must be in the inclusive range 1..128")
    return value


def _gwyddion_physical_to_pixel(value: float, resolution: int, real_extent: float) -> float:
    """Map a physical coordinate to the Gwyddion data-field pixel coordinate."""
    return value * resolution / real_extent


def _gwyddion_c_trunc_div(numerator: int, denominator: int) -> int:
    """Return C signed-integer division truncated toward zero."""
    if denominator == 0:
        raise ZeroDivisionError("Gwyddion Path Level line division by zero")
    magnitude = abs(numerator) // abs(denominator)
    return -magnitude if (numerator < 0) != (denominator < 0) else magnitude


def _gwyddion_normalized_path_level_lines(
    lines: Sequence[_GwyddionPathLevelLine],
    *,
    xres: int,
    yres: int,
    xreal: float,
    yreal: float,
) -> tuple[_NormalizedLine, ...]:
    """Convert ordered physical selections to source-equivalent integer endpoints."""
    result: list[_NormalizedLine] = []
    for line in lines:
        x0 = math.floor(_gwyddion_physical_to_pixel(line.x0, xres, xreal))
        y0 = math.floor(_gwyddion_physical_to_pixel(line.y0, yres, yreal))
        x1 = math.floor(_gwyddion_physical_to_pixel(line.x1, xres, xreal))
        y1 = math.floor(_gwyddion_physical_to_pixel(line.y1, yres, yreal))
        if y0 > y1:
            x0, x1 = x1, x0
            y0, y1 = y1, y0
        result.append(
            (
                min(max(int(x0), 0), xres - 1),
                min(max(math.floor(y0), 0), yres - 1),
                min(max(int(x1), 0), xres - 1),
                min(max(math.ceil(y1), 0), yres - 1),
            )
        )
    return tuple(result)


def _validated_extent(value: object, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        raise TypeError(f"Gwyddion Path Level {name} must be a real scalar")
    try:
        extent = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"Gwyddion Path Level {name} must be a real scalar") from exc
    if not math.isfinite(extent) or extent <= 0.0:
        raise ValueError(f"Gwyddion Path Level {name} must be finite and positive")
    return extent


def _line_column(line: _NormalizedLine, row: int) -> int:
    x0, y0, x1, y1 = line
    horizontal_span = x1 - x0
    vertical_span = y1 - y0
    orientation = 1 if vertical_span > 0 else -1
    numerator = (2 * (row - y0) + 1) * horizontal_span + orientation * vertical_span
    denominator = 2 * orientation * vertical_span
    return _gwyddion_c_trunc_div(numerator, denominator) + x0


def _gwyddion_path_level_result(
    data: ArrayLike,
    lines: object,
    *,
    xreal: object,
    yreal: object,
    thickness_px: object,
) -> _GwyddionPathLevelResult:
    """Compute the frozen Gwyddion 2.71 Path Level corrected field privately."""
    values = _validated_gwyddion_path_level_data(data)
    physical_lines = _validated_gwyddion_path_level_lines(lines)
    thickness = _validated_gwyddion_path_level_thickness(thickness_px)
    horizontal_extent = _validated_extent(xreal, "xreal")
    vertical_extent = _validated_extent(yreal, "yreal")
    yres, xres = values.shape
    normalized = _gwyddion_normalized_path_level_lines(
        physical_lines,
        xres=xres,
        yres=yres,
        xreal=horizontal_extent,
        yreal=vertical_extent,
    )
    changes = sorted(
        [(line[1], False, identifier) for identifier, line in enumerate(normalized)]
        + [(line[3], True, identifier) for identifier, line in enumerate(normalized)]
    )
    active = [False] * len(normalized)
    row_differences = np.zeros(yres, dtype=np.float64)
    lower_reach = (thickness - 1) // 2
    upper_reach = thickness // 2
    change_index = 0

    for row in range(yres):
        if row:
            total = np.float64(0.0)
            count = 0
            for identifier, line in enumerate(normalized):
                if active[identifier]:
                    column = _line_column(line, row)
                    first = max(0, column - lower_reach)
                    last = min(xres - 1, column + upper_reach)
                    for sample_column in range(first, last + 1):
                        difference = values[row, sample_column] - values[row - 1, sample_column]
                        total = total + difference
                        count += 1
            if count:
                row_differences[row] = total / np.float64(count)
        while change_index < len(changes) and changes[change_index][0] == row:
            _, is_end, identifier = changes[change_index]
            active[identifier] = not is_end
            change_index += 1

    cumulative = np.zeros(yres, dtype=np.float64)
    running = np.float64(0.0)
    for row in range(yres):
        running = running + row_differences[row]
        cumulative[row] = running
    corrected = values.copy(order="C")
    for row in range(yres):
        for column in range(xres):
            corrected[row, column] = corrected[row, column] - cumulative[row]
    return _GwyddionPathLevelResult(
        corrected=corrected,
        normalized_lines=normalized,
        row_differences=row_differences,
        cumulative_row_correction=cumulative,
        thickness_px=thickness,
    )
