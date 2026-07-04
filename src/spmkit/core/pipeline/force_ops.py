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
from spmkit.core.analysis import mechanics
from spmkit.core.models import ForceCurve
from spmkit.core.pipeline.operations import operation


def _resolve(value: Any, from_metadata: Any) -> Any:
    """Resuelve un parámetro ``"from_metadata"`` al valor de los metadatos."""
    return from_metadata if value == "from_metadata" else value


def _primary_segment(curve: ForceCurve) -> Any:
    return curve.extend or (curve.segments[0] if curve.segments else None)


def _indentation_axis(seg: Any) -> Any:
    """Eje ``x`` para el ajuste, orientado como espera :mod:`mechanics`.

    La nanomecánica de ``mechanics`` supone "x creciente ⇒ más indentación". En una
    curva de fuerza eso corresponde a la **separación punta-muestra decreciente**
    (el piezo empuja hacia la muestra), así que se usa ``-separación``. Como la
    separación ya corrige la flexión del cantiléver, el ajuste NO vuelve a corregir
    por ``k``. Sin separación (curva no calibrada), cae a ``-raw_height``.
    """
    sep = seg.separation if seg.separation is not None else seg.raw_height
    return -sep


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
    if inv is None or k is None:
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
    mech = mechanics.ForceCurve(z=_indentation_axis(seg), force=seg.force)
    corrected = mechanics.baseline_correct(mech)
    z0 = mechanics.find_contact_point(corrected, method=method)
    ctx["contact_point"] = float(z0)
    ctx["contact_detected"] = True
    return curve


@operation("fit_elasticity")
def fit_elasticity(
    curve: ForceCurve,
    ctx: dict[str, Any],
    model: str = "sphere",
    tip_radius: float = 10e-9,
    poisson: float = 0.3,
) -> ForceCurve:
    """Ajusta un modelo de contacto al segmento de aproximación.

    Usa el punto de contacto de ``ctx`` si está (de ``find_contact_point``), o lo
    detecta. Escribe ``ctx["young_modulus"]``, ``ctx["r_squared"]``, ``ctx["adhesion"]``
    y el objeto completo en ``ctx["fit"]``.
    """
    seg = _primary_segment(curve)
    if seg is None:
        raise ValueError("fit_elasticity: la curva no tiene segmentos")
    force = seg.require_force()
    mech = mechanics.ForceCurve(z=_indentation_axis(seg), force=force)
    # La separación ya corrige la flexión → no volver a corregir por k aquí.
    result = mechanics.fit_hertz(
        mech,
        tip_radius=tip_radius,
        model=model,
        poisson=poisson,
        spring_constant=None,
        contact_point=ctx.get("contact_point"),
    )
    ctx["young_modulus"] = result.young_modulus
    ctx["young_modulus_std"] = result.young_modulus_std
    ctx["r_squared"] = result.r_squared
    ctx["adhesion"] = result.adhesion
    ctx["fit"] = result
    return curve
