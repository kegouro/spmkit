"""Candidate windows on native, calibrated approach/retract arrays (SI)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
from scipy.ndimage import median_filter
from scipy.optimize import minimize_scalar

from spmkit.core.analysis.contact_mechanics import forward_model
from spmkit.core.analysis.force_contact import contact_point_threshold
from spmkit.core.analysis.force_steps import measure_force_step
from spmkit.core.models import ForceCurve, ForceSegment


@dataclass(frozen=True)
class WindowOptions:
    mode: Literal["steps", "contact"]
    branch: Literal["extend", "retract"] = "extend"
    flank: int = 8
    sigma: float = 6.0
    tip_radius_nm: float = 10.0
    poisson: float = 0.3
    max_depth_nm: float = 5.0

    def __post_init__(self) -> None:
        if self.mode not in ("steps", "contact") or self.branch not in ("extend", "retract"):
            raise ValueError("Modo o rama desconocidos")
        if self.mode == "contact" and self.branch != "extend":
            raise ValueError("El ajuste de contacto requiere aproximación")
        if self.flank < 4 or not 3 <= self.sigma <= 20:
            raise ValueError("Ventana o umbral inválido")
        if not (
            0 < self.tip_radius_nm < np.inf
            and 0 < self.max_depth_nm < np.inf
            and 0 <= self.poisson < 0.5
        ):
            raise ValueError("Geometría de contacto inválida")


@dataclass(frozen=True)
class AutoWindow:
    start: int
    end: int  # inclusive indices in acquisition order
    boundary: int
    sensor_start_m: float
    sensor_end_m: float
    delta_force_n: float | None = None
    modulus_pa: float | None = None
    residual_rms_n: float | None = None
    r_squared: float | None = None
    axis: str = "sensor_height"
    detection_threshold_n: float | None = None
    contact_origin_travel_m: float | None = None


def _mad(a: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(a - np.median(a))))


def _steps(seg: ForceSegment, z: np.ndarray, f: np.ndarray, o: WindowOptions) -> list[AutoWindow]:
    # A large adjacent difference is only a proposal. Remove the local ramp slope
    # first, then verify the change independently on short and full flanks.
    w = o.flank
    if len(f) < 2 * w:
        raise ValueError("Faltan muestras a ambos lados")
    dz = np.diff(z)
    if not (np.any(dz > 0) or np.any(dz < 0)):
        raise ValueError("La altura del sensor es constante")
    diff = np.diff(f)
    slope = np.divide(diff, dz, out=np.zeros_like(diff), where=dz != 0)
    innovation = diff - median_filter(slope, size=2 * w - 1, mode="nearest") * dz
    floor = np.finfo(float).eps * max(np.max(np.abs(f)), np.finfo(float).tiny) * 64
    threshold = max(o.sigma * _mad(innovation), floor)
    peaks = np.flatnonzero(np.abs(innovation) > threshold) + 1
    events = []
    for j, index in enumerate(peaks):
        i = int(index)
        if i < w or i + w > len(f):
            continue
        if (j and i - peaks[j - 1] < w) or (j + 1 < len(peaks) and peaks[j + 1] - i < w):
            continue  # spike pair or unresolved neighbours
        try:
            full = measure_force_step(seg, i, w)
            short = measure_force_step(seg, i, max(3, w // 2))
        except ValueError:
            continue
        jump = full.delta_force_n
        rms = max(full.left_residual_rms_n, full.right_residual_rms_n)
        if abs(jump) <= max(threshold, o.sigma * rms) or abs(
            jump - short.delta_force_n
        ) > 0.25 * abs(jump):
            continue
        events.append(
            AutoWindow(
                i - w,
                i + w - 1,
                i,
                float(z[i - w]),
                float(z[i + w - 1]),
                delta_force_n=jump,
                detection_threshold_n=threshold,
                residual_rms_n=rms,
            )
        )
    return events


def _contact(seg: ForceSegment, z: np.ndarray, f: np.ndarray, o: WindowOptions) -> AutoWindow:
    # Locate sustained repulsion against an extrapolated pre-contact baseline.
    n = len(f)
    nbase = max(8, n // 10)
    if n < 40 or not (np.all(np.diff(z) > 0) or np.all(np.diff(z) < 0)):
        raise ValueError("Aproximación corta o altura no monótona")
    travel = (z - z[0]) * np.sign(z[-1] - z[0])
    slope, offset = np.polyfit(travel[:nbase], f[:nbase], 1)
    signal = f - (offset + slope * travel)
    corrected = replace(seg, force=signal)
    crossing = contact_point_threshold(ForceCurve((corrected,)), threshold_sigma=o.sigma)
    if not crossing.valid or crossing.index <= nbase:
        raise ValueError("Sin contacto repulsivo persistente tras la línea base")
    if seg.separation is not None and seg.metadata.get("separation_status") != "unverified":
        sep = np.asarray(seg.separation, dtype=float)
        x = (sep - sep[0]) * np.sign(sep[crossing.index] - sep[0])
        axis = "separation"
    elif seg.deflection is not None:
        x = travel - (seg.deflection - seg.deflection[0])
        axis = "travel_minus_deflection"
    else:
        raise ValueError("Falta separación contrastada o deflexión calibrada")

    if not np.isfinite(x).all() or not np.all(np.diff(x) > 0):
        raise ValueError("Coordenada de indentación no monótona")
    # Compare candidate origins on the SAME data. Distances are scaled to nm
    # for the optimizer. Radius and Poisson enter through the core Hertz model.
    x = x * 1e9
    i = crossing.index
    margin = max(4, n // 20)
    lower, upper = max(nbase, i - margin), min(n - 1, i + margin)
    stop = min(n, int(np.searchsorted(x, x[i] + o.max_depth_nm, side="right")))
    upper = min(upper, stop - 10)
    if upper <= i or stop - i < 12:
        raise ValueError("Profundidad o muestras insuficientes para resolver el contacto")
    xx, yy = x[lower:stop], signal[lower:stop]
    fixed = {"R": o.tip_radius_nm * 1e-9, "poisson": o.poisson, "E": 1.0}

    def fit_at(xx: np.ndarray, yy: np.ndarray, origin: float) -> tuple[float, np.ndarray]:
        basis = forward_model("hertz_sphere", np.maximum(xx - origin, 0) * 1e-9, fixed)
        e = float(np.dot(basis, yy) / np.dot(basis, basis))
        return e, yy - e * basis

    def objective(origin: float) -> float:
        return float(np.mean(np.square(fit_at(xx, yy, origin)[1])))

    fit = minimize_scalar(
        objective,
        bounds=(x[lower], x[upper]),
        method="bounded",
        options={"xatol": max((x[upper] - x[lower]) * 1e-7, 1e-12)},
    )
    origin = float(fit.x)
    boundary = int(np.searchsorted(x, origin))
    if not fit.success or not lower < boundary < upper:
        raise ValueError("Origen Hertz incompatible con el contacto detectado")
    # Refit E only on post-contact points in the stated depth window.
    end = int(np.searchsorted(x, origin + o.max_depth_nm, side="right"))
    xx, yy = x[boundary:end], signal[boundary:end]
    if len(xx) < 12:
        raise ValueError("Ventana de contacto demasiado corta")
    modulus, residual = fit_at(xx, yy, origin)
    mid = len(xx) // 2
    e_left, _ = fit_at(xx[:mid], yy[:mid], origin)
    e_right, _ = fit_at(xx[mid:], yy[mid:], origin)
    if abs(e_right - e_left) > 0.25 * abs(modulus):
        raise ValueError("Módulo inestable entre las dos mitades de la ventana")
    total = float(np.sum((yy - yy.mean()) ** 2))
    r2 = 1 - float(np.sum(residual**2)) / total if total else 0.0
    if not (np.isfinite(modulus) and modulus > 0 and r2 >= 0.98):
        raise ValueError(
            "La ventana no describe un contacto Hertz estable (R² < 0.98 o E inválido)"
        )
    return AutoWindow(
        boundary,
        end - 1,
        boundary,
        float(z[boundary]),
        float(z[end - 1]),
        modulus_pa=modulus,
        residual_rms_n=float(np.sqrt(np.mean(residual**2))),
        r_squared=r2,
        axis=axis,
        contact_origin_travel_m=origin * 1e-9,
    )


def select_windows(curve: ForceCurve, options: WindowOptions) -> list[AutoWindow]:
    seg = curve.segment(options.branch, 0)
    if seg is None or seg.state != "force_n" or seg.force is None:
        raise ValueError("Falta la rama de fuerza calibrada")
    f, z = np.asarray(seg.force, dtype=float), np.asarray(seg.raw_height, dtype=float)
    if f.ndim != 1 or z.shape != f.shape or not np.isfinite(f).all() or not np.isfinite(z).all():
        raise ValueError("Muestras no finitas o canales incompatibles")
    if options.mode == "steps":
        return _steps(seg, z, f, options)
    return [_contact(seg, z, f, options)]
