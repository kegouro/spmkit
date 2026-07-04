"""Ejecución de un :class:`Recipe` sobre un objetivo (curva de fuerza).

``run`` corre los pasos en orden, saltando los que tengan una ``condition`` que no se
cumpla contra el contexto acumulado. Acepta un ``progress`` callback para que la GUI
avance una barra sin acoplar ``core`` a Qt. La ejecución paralela sobre un
``ForceVolume`` (con ``ProcessPoolExecutor``) se añade en una fase posterior; el
contrato del callback ya está pensado para ese caso (se invoca desde el proceso
principal a medida que llegan los resultados).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from spmkit.core.pipeline.operations import get_operation
from spmkit.core.pipeline.recipe import Recipe, evaluate_condition

#: Callback de progreso: ``(fracción_completada ∈ [0, 1], nombre_del_paso)``.
ProgressCallback = Callable[[float, str], None]


def run(
    recipe: Recipe,
    target: Any,
    *,
    context: dict[str, Any] | None = None,
    progress: ProgressCallback | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Corre el ``recipe`` sobre ``target`` y devuelve ``(resultado, contexto)``.

    Args:
        recipe: El pipeline a ejecutar.
        target: Objetivo inicial (p. ej. una ``ForceCurve``).
        context: Contexto inicial (campos que las condiciones pueden consultar).
        progress: Callback opcional invocado tras cada paso ejecutado.
    """
    ctx: dict[str, Any] = dict(context or {})
    result = target
    total = len(recipe.steps)
    for i, step in enumerate(recipe.steps):
        if step.condition is not None and not evaluate_condition(step.condition, ctx):
            continue
        fn = get_operation(step.op)
        result = fn(result, ctx, **step.params)
        if progress is not None:
            progress((i + 1) / total if total else 1.0, step.op)
    return result, ctx
