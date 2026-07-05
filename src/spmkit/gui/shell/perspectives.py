"""Perspectivas del workspace — presets de paneles por tarea.

Reemplazan las 7 pestañas planas: el usuario cambia de *tarea* (perspectiva), no de
pestaña. Cada perspectiva declara qué paneles muestra; el :class:`~spmkit.gui.shell.
workspace.Workspace` muestra/oculta los docks correspondientes al activarla.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Perspective:
    """Un preset de layout: qué paneles se muestran para una tarea."""

    key: str
    label: str
    panels: tuple[str, ...]  # claves de panel a mostrar


#: Etiqueta legible de cada panel (para docks y la paleta de comandos).
PANEL_LABELS: dict[str, str] = {
    "navigator": "Datos",
    "inspector": "Inspector",
    "pipeline": "Pipeline",
    "image_canvas": "Imagen",
    "force_canvas": "Curva de fuerza",
    "map_canvas": "Mapa",
    "histogram": "Histograma",
    "batch_table": "Batch",
    "figure_editor": "Figura",
    "simulator": "Simulador",
    "log": "Log",
}

#: Perspectivas de fábrica, en orden de la barra superior.
PERSPECTIVES: tuple[Perspective, ...] = (
    Perspective("image", "Imagen", ("navigator", "image_canvas", "inspector")),
    Perspective("force", "Curva de fuerza", ("navigator", "force_canvas", "inspector", "pipeline")),
    Perspective("map", "Mapa", ("navigator", "map_canvas", "inspector", "histogram")),
    Perspective("batch", "Batch", ("navigator", "batch_table", "log")),
    Perspective("figure", "Figura", ("figure_editor", "inspector")),
    Perspective("simulator", "Simulador", ("simulator",)),
)

#: Todos los paneles que alguna perspectiva usa (unión, orden estable).
ALL_PANELS: tuple[str, ...] = tuple(
    dict.fromkeys(panel for p in PERSPECTIVES for panel in p.panels)
)


def perspective(key: str) -> Perspective:
    """Devuelve la perspectiva con esa clave o lanza ``KeyError``."""
    for p in PERSPECTIVES:
        if p.key == key:
            return p
    raise KeyError(f"perspectiva desconocida: {key!r}")
