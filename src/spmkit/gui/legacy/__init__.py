"""App clásica de spmkit (7 pestañas) — **conservada como legacy**.

Fue la primera interfaz (Visor, Nanomecánica, Vista 3D, Resonancia, Simulador, Editor de
figuras, Comparar). El default ahora es **Fathom** (``spmkit gui`` / ``spmkit workspace``);
esta app se conserva intacta y documentada como fallback y referencia, lanzable con
``spmkit gui --legacy``. Su funcionalidad se migra a perspectivas MVVM de Fathom por fases
(ver ``docs/design/ROADMAP.md`` F2/F3); hasta entonces sigue disponible sin cambios.

Sigue respetando la separación de capas: importa sólo la API pública de ``core``.
"""

from spmkit.gui.legacy.app import run

__all__ = ["run"]
