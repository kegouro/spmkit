"""Perspectivas del workspace — **derivadas de los módulos de fábrica**.

Ya no hay una lista hardcodeada: las perspectivas, etiquetas de panel y áreas de dock se
derivan de :data:`~spmkit.gui.builtin_modules.BUILTIN_MODULES` (ver
:mod:`spmkit.gui.extensions`). Añadir una perspectiva = añadir un ``ModuleSpec``; esta capa
la recoge sola. Se conservan los nombres públicos (``PERSPECTIVES``, ``PANEL_LABELS``,
``ALL_PANELS``, ``perspective``) por compatibilidad con la shell y los tests.
"""

from __future__ import annotations

from spmkit.gui.builtin_modules import BUILTIN_MODULES
from spmkit.gui.extensions import PerspectiveSpec as Perspective
from spmkit.gui.extensions import spec_metadata

# Derivado de los módulos de fábrica (fuente única de verdad).
PERSPECTIVES, PANEL_LABELS, DOCK_AREAS, CENTRAL_PANELS = spec_metadata(BUILTIN_MODULES)

#: Todos los paneles que alguna perspectiva usa (unión, orden estable).
ALL_PANELS: tuple[str, ...] = tuple(PANEL_LABELS)

__all__ = [
    "Perspective",
    "PERSPECTIVES",
    "PANEL_LABELS",
    "DOCK_AREAS",
    "CENTRAL_PANELS",
    "ALL_PANELS",
    "perspective",
]


def perspective(key: str) -> Perspective:
    """Devuelve la perspectiva con esa clave o lanza ``KeyError``."""
    for p in PERSPECTIVES:
        if p.key == key:
            return p
    raise KeyError(f"perspectiva desconocida: {key!r}")
