"""Operaciones reales del pipeline sobre curvas de fuerza (Fase 2).

Registran, vía :func:`operation`, los pasos que un :class:`Recipe` encadena para
analizar una :class:`ForceCurve`: **calibrar** (V→m→N), **detectar contacto** y
**ajustar elasticidad**. Reutilizan la nanomecánica ya validada de
:mod:`spmkit.core.analysis.mechanics`.

Contrato de una operación: ``op(curve, ctx, **params) -> curve``. La op puede
escribir en ``ctx`` (para condiciones de pasos posteriores y para exponer
resultados) y devuelve la curva, posiblemente transformada (inmutable: se crea una
copia con :func:`dataclasses.replace`).

Importar este módulo registra las operaciones; ``spmkit.core.pipeline`` lo hace por
ti, de modo que están disponibles al usar el motor de pipeline.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from spmkit.core.analysis import calibration as _cal
from spmkit.core.analysis import forcecurve
from spmkit.core.models import ForceCurve
from spmkit.core.pipeline.operations import operation


def _resolve(value: Any, from_metadata: Any) -> Any:
    """Resuelve un parámetro ``"from_metadata"`` al valor de los metadatos."""
    return from_metadata if value == "from_metadata" else value


def _primary_segment(curve: ForceCurve) -> Any:
    return curve.extend or (curve.segments[0] if curve.segments else None)


def _axis(seg: Any) -> Any:
    """Eje del ajuste (ver :func:`forcecurve.display_axis`): separación o altura."""
    return forcecurve.display_axis(seg.separation, seg.raw_height)


@operation("calibrate")
def calibrate(
    curve: ForceCurve,
    ctx: dict[str, Any],
    invols: Any = "from_metadata",
    spring_constant: Any = "from_metadata",
) -> ForceCurve:
    """Convierte los segmentos a fuerza (N): ``V → m (InVOLS) → N (k)``.

    ``invols``/``spring_constant`` pueden ser numéricos o ``"from_metadata"`` (leerlos
    de ``curve.calibration``). Los segmentos que ya tienen ``force`` pasan sin cambio.
    """
    cal = curve.calibration
    inv = _resolve(invols, cal.invols if cal else None)
    k = _resolve(spring_constant, cal.spring_constant if cal else None)
    # Solo se necesita calibración si algún segmento aún no tiene fuerza (V/m crudos).
    needs_calibration = any(seg.force is None for seg in curve.segments)
    if needs_calibration and (inv is None or k is None):
        raise ValueError("calibrate: faltan invols/k (ni en params ni en curve.calibration)")

    new_segments = []
    for seg in curve.segments:
        if seg.force is not None:
            new_segments.append(seg)
            continue
        deflection = _cal.volts_to_deflection(seg.raw_deflection, inv)
        force = _cal.deflection_to_force(deflection, k)
        new_segments.append(
            replace(
                seg,
                deflection=deflection,
                force=force,
                separation=seg.raw_height - deflection,
                state="force_n",
            )
        )
    ctx["calibrated"] = True
    ctx["invols"] = inv
    ctx["spring_constant"] = k
    return replace(curve, segments=tuple(new_segments))


@operation("smooth")
def smooth(
    curve: ForceCurve, ctx: dict[str, Any], window: int = 11, polyorder: int = 3
) -> ForceCurve:
    """Suaviza la fuerza de cada segmento con Savitzky-Golay (opcional, como ANA/JPK).

    ``window`` se fuerza impar; con menos de 3 (o segmentos cortos) es un no-op. Reduce
    el ruido antes del ajuste; úsalo con criterio (un suavizado agresivo sesga el módulo).
    """
    from scipy.signal import savgol_filter

    w = int(window)
    if w < 3:
        return curve
    if w % 2 == 0:
        w += 1
    new_segments = []
    for seg in curve.segments:
        if seg.force is not None and seg.force.size > w:
            po = min(int(polyorder), w - 1)
            new_segments.append(replace(seg, force=savgol_filter(seg.force, w, po)))
        else:
            new_segments.append(seg)
    ctx["smoothed"] = w
    return replace(curve, segments=tuple(new_segments))


@operation("find_contact_point")
def find_contact_point(curve: ForceCurve, ctx: dict[str, Any], method: str = "rov") -> ForceCurve:
    """Detecta el punto de contacto del segmento de aproximación.

    Escribe ``ctx["contact_detected"]`` y ``ctx["contact_point"]`` (m). Requiere que
    el segmento esté calibrado (con fuerza).
    """
    seg = _primary_segment(curve)
    if seg is None or seg.force is None:
        ctx["contact_detected"] = False
        return curve
    ctx["contact_point"] = forcecurve.find_contact(_axis(seg), seg.force)
    ctx["contact_detected"] = True
    return curve


@operation("fit_elasticity")
def fit_elasticity(
    curve: ForceCurve,
    ctx: dict[str, Any],
    model: str = "sphere",
    tip_radius: float = 10e-9,
    poisson: float = 0.3,
    half_angle: float | None = None,
    fit_range: tuple[float, float] | None = None,
    contact_method: str = "joint",
    k_sigma: float = 5.0,
    mc: bool = False,
    invols_rel_err: float = 0.05,
    k_rel_err: float = 0.05,
    mc_samples: int = 200,
    mc_seed: int = 0,
) -> ForceCurve:
    """Ajusta un modelo de contacto al segmento de aproximación.

    Usa el punto de contacto de ``ctx`` si está (de ``find_contact_point``), o lo
    detecta. Escribe ``ctx["young_modulus"]``, ``ctx["r_squared"]``, ``ctx["adhesion"]``
    y el objeto completo en ``ctx["fit"]``. ``half_angle`` (rad) sólo aplica al modelo
    ``cone``; ``None`` usa el valor por defecto del core. ``fit_range`` (min, max en m)
    restringe el ajuste a una ventana manual del eje. ``contact_method`` (``"joint"`` /
    ``"threshold"``) elige la detección de contacto; ``k_sigma`` es su umbral de ruido.
    Con ``mc=True`` propaga la incertidumbre de InVOLS/k por Monte Carlo (``mc_samples``
    muestras) y escribe ``ctx["young_modulus_std"]`` (Pa).
    """
    seg = _primary_segment(curve)
    if seg is None:
        raise ValueError("fit_elasticity: la curva no tiene segmentos")
    force = seg.require_force()
    extra: dict[str, Any] = {"contact_method": contact_method, "k_sigma": k_sigma}
    if half_angle is not None:
        extra["half_angle"] = half_angle
    if fit_range is not None:
        extra["fit_range"] = tuple(fit_range)
    fit = forcecurve.fit_force_curve(
        _axis(seg), force, model=model, tip_radius=tip_radius, poisson=poisson, **extra
    )
    ctx["young_modulus"] = fit.young_modulus
    ctx["young_modulus_std"] = fit.young_modulus_std
    if mc:
        _, ctx["young_modulus_std"] = forcecurve.fit_force_curve_mc(
            _axis(seg),
            force,
            invols_rel_err=invols_rel_err,
            k_rel_err=k_rel_err,
            n_samples=mc_samples,
            seed=mc_seed,
            model=model,
            tip_radius=tip_radius,
            poisson=poisson,
            **extra,
        )
    ctx["r_squared"] = fit.r_squared
    ctx["contact_point"] = fit.contact_point
    ctx["adhesion"] = fit.adhesion
    ctx["max_indentation"] = fit.max_indentation
    ctx["max_force"] = fit.max_force
    ctx["fit"] = fit

    # Energía de disipación (histéresis) si hay segmento de retract.
    retract = curve.retract
    if retract is not None and retract.force is not None:
        ctx["dissipation"] = forcecurve.dissipation_energy(
            _axis(seg), force, _axis(retract), retract.force
        )
    return curve
