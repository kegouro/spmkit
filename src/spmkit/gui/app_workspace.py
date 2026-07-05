"""Ensamblado del nuevo workspace (rediseño): VM de fuerza + paneles reales.

Punto de entrada del rediseño. Construye el :class:`ForceViewModel`, cablea los
paneles de la perspectiva de curva de fuerza (lienzo, inspector, navegador) y añade
el comando "Abrir…" (``QFileDialog`` → :func:`load_force`). Las demás perspectivas
siguen con placeholders hasta sus fases.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QFileDialog

from spmkit.core.io import load_force, supported_force_extensions
from spmkit.gui.panels.force_canvas import ForceCanvasPanel
from spmkit.gui.panels.inspector import InspectorPanel
from spmkit.gui.panels.navigator import NavigatorPanel
from spmkit.gui.shell.command_palette import Command
from spmkit.gui.shell.workspace import Workspace
from spmkit.gui.viewmodels import ForceViewModel


def build_workspace(mode: str = "dark") -> Workspace:
    """Construye el workspace con la perspectiva de curva de fuerza cableada."""
    vm = ForceViewModel()
    panels = {
        "force_canvas": ForceCanvasPanel(vm),
        "inspector": InspectorPanel(vm),
        "navigator": NavigatorPanel(vm),
    }
    ws = Workspace(panels=panels, mode=mode)
    ws.register_command(Command("Abrir curva/volumen…", lambda: _open_dialog(ws, vm), "Ctrl+O"))
    return ws


def _open_dialog(ws: Workspace, vm: ForceViewModel) -> None:
    exts = " ".join(f"*{e}" for e in supported_force_extensions())
    path, _ = QFileDialog.getOpenFileName(
        ws, "Abrir curva de fuerza", "", f"Curvas de fuerza ({exts})"
    )
    if not path:
        return
    try:
        vm.set_volume(load_force(path))
    except Exception as exc:  # noqa: BLE001 - error de IO se muestra, no tumba la app
        ws.show_status(f"No se pudo abrir {Path(path).name}: {exc}")
        return
    ws.set_perspective("force")
    ws.show_status(f"{Path(path).name} — {vm.n_curves} curva(s)")


def main() -> int:
    """Lanza el workspace del rediseño como app independiente."""
    app = QApplication.instance() or QApplication(sys.argv)
    ws = build_workspace()
    ws.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
