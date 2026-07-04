"""``Recipe``: pipeline de análisis serializable (la pieza maestra de spmkit).

Un ``Recipe`` es una lista ordenada de pasos ``(op, params, condition)`` que corre
igual sobre una curva, un force-map o un batch. Es serializable a YAML (legible y
editable a mano), de modo que la GUI puede *grabar* lo que hace el usuario y que un
análisis sea reproducible y compartible.

Las condiciones (``fit_elasticity`` solo si hubo contacto, etc.) se evalúan con un
**evaluador restringido basado en ``ast``**, NUNCA con ``eval()``: un ``recipe.yaml``
es un archivo externo y evaluar strings arbitrarios sería un hueco de seguridad.
Solo se permiten nombres de una lista blanca (el contexto de resultados), literales,
comparaciones (``== != < <= > >=``) y booleanos (``and``/``or``/``not``).
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from typing import Any

import yaml

_ALLOWED_CMP = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def evaluate_condition(expr: str, context: dict[str, Any]) -> bool:
    """Evalúa una condición booleana restringida contra ``context``.

    Solo admite nombres presentes en ``context`` (lista blanca), literales,
    comparaciones y ``and``/``or``/``not``. Cualquier otra construcción (llamadas a
    función, atributos, índices, etc.) lanza ``ValueError``. No usa ``eval()``.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Condición inválida: {expr!r} ({exc})") from exc
    return bool(_eval_node(tree.body, context))


def _eval_node(node: ast.AST, ctx: dict[str, Any]) -> Any:
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, ctx) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError("Operador booleano no permitido en condición.")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, ctx)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            fn = _ALLOWED_CMP.get(type(op))
            if fn is None:
                raise ValueError(f"Operador de comparación no permitido: {type(op).__name__}")
            right = _eval_node(comparator, ctx)
            if not fn(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        if node.id in ctx:
            return ctx[node.id]
        raise ValueError(f"Nombre no permitido en condición: {node.id!r}")
    if isinstance(node, ast.Constant):
        return node.value
    raise ValueError(f"Expresión no permitida en condición: {type(node).__name__}")


@dataclass(frozen=True)
class Step:
    """Un paso del pipeline: operación, parámetros y condición opcional."""

    op: str
    params: dict[str, Any] = field(default_factory=dict)
    condition: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"op": self.op}
        if self.params:
            d["params"] = dict(self.params)
        if self.condition:
            d["condition"] = self.condition
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Step:
        if "op" not in data:
            raise ValueError(f"Paso sin clave 'op': {data!r}")
        return cls(
            op=str(data["op"]),
            params=dict(data.get("params", {})),
            condition=data.get("condition"),
        )


@dataclass(frozen=True)
class Recipe:
    """Pipeline de análisis reproducible: pasos ordenados, serializable a YAML."""

    steps: tuple[Step, ...]
    name: str = "recipe"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "steps": [s.to_dict() for s in self.steps]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recipe:
        steps = tuple(Step.from_dict(s) for s in data.get("steps", []))
        return cls(steps=steps, name=str(data.get("name", "recipe")))

    def to_yaml(self) -> str:
        """Serializa el recipe a YAML (orden de claves estable)."""
        return yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, text: str) -> Recipe:
        """Reconstruye un recipe desde YAML."""
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("El YAML del recipe debe ser un mapeo con 'name' y 'steps'.")
        return cls.from_dict(data)
