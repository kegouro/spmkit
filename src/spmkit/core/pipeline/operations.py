"""Registro de operaciones del pipeline.

Cada operación es una función pura ``(target, context, **params) -> target`` que
transforma el objetivo (una ``ForceCurve``, por ahora) y puede escribir campos en
``context`` (p. ej. ``contact_detected``, ``r_squared``) que las condiciones de pasos
posteriores consultan. Las operaciones reales de física (calibrate, baseline_correct,
find_contact_point, fit_elasticity, ...) se registran aquí en fases posteriores.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

#: Nombre de operación → función ``(target, context, **params) -> target``.
Operation = Callable[..., Any]
_REGISTRY: dict[str, Operation] = {}


def operation(name: str) -> Callable[[Operation], Operation]:
    """Decorador para registrar una operación bajo ``name``."""

    def decorator(fn: Operation) -> Operation:
        if name in _REGISTRY:
            raise ValueError(f"Operación ya registrada: {name!r}")
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_operation(name: str) -> Operation:
    """Devuelve la operación registrada ``name`` o lanza ``KeyError``."""
    if name not in _REGISTRY:
        raise KeyError(f"Operación desconocida: {name!r}. Disponibles: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def available_operations() -> list[str]:
    """Lista los nombres de operaciones registradas."""
    return sorted(_REGISTRY)
