"""Measure a pre-annotated force discontinuity on one acquisition branch."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spmkit.core.models import ForceSegment


@dataclass(frozen=True)
class ForceStep:
    height_m: float
    delta_force_n: float
    left_slope_n_per_m: float
    right_slope_n_per_m: float
    left_residual_rms_n: float
    right_residual_rms_n: float


def measure_force_step(segment: ForceSegment, boundary: int, window: int) -> ForceStep:
    """Difference of two local lines at the midpoint of the boundary height interval.

    Boundary is the first sample after the proposed jump in acquisition order.
    Each side uses exactly window samples. Residual RMS is descriptive.
    """
    if segment.state != "force_n":
        raise ValueError("Se requiere fuerza calibrada en N")
    z = np.asarray(segment.raw_height, dtype=float)
    f = np.asarray(segment.require_force(), dtype=float)
    if z.ndim != 1 or z.shape != f.shape:
        raise ValueError("Canales de altura y fuerza incompatibles")
    if window < 3 or boundary < window or boundary + window > len(z):
        raise ValueError("Se requieren dos ventanas completas de al menos tres muestras")
    region = slice(boundary - window, boundary + window)
    z, f = z[region], f[region]
    if not np.all(np.isfinite(z)) or not np.all(np.isfinite(f)):
        raise ValueError("Muestras no finitas en las ventanas")
    dz = np.diff(z)
    if not (np.all(dz > 0) or np.all(dz < 0)):
        raise ValueError("La altura debe ser estrictamente monótona en ambas ventanas")
    midpoint = z[window - 1] + dz[window - 1] / 2

    def line(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
        centered = x - x.mean()
        slope = float(np.dot(centered, y - y.mean()) / np.dot(centered, centered))
        value = y.mean() + slope * (midpoint - x.mean())
        residual = y - (value + slope * (x - midpoint))
        return float(value), slope, float(np.sqrt(np.mean(residual**2)))

    with np.errstate(over="raise", divide="raise", invalid="raise"):
        before, left, rms_l = line(z[:window], f[:window])
        after, right, rms_r = line(z[window:], f[window:])
    jump = after - before
    if not np.isfinite(jump):
        raise ValueError("Salto fuera del rango numérico")
    return ForceStep(float(midpoint), jump, left, right, rms_l, rms_r)


def boundary_sensitivity(
    segment: ForceSegment, boundary: int, window: int
) -> list[dict[str, int | float | str]]:
    """Repeat the same fit one acquisition sample before and after the annotation."""
    trials: list[dict[str, int | float | str]] = []
    for offset in (-1, 1):
        try:
            fit = measure_force_step(segment, boundary + offset, window)
            trials.append({"offset_samples": offset, "delta_force_n": fit.delta_force_n})
        except (ValueError, FloatingPointError) as exc:
            trials.append({"offset_samples": offset, "reason": str(exc)})
    return trials
