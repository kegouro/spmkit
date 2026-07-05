"""Ensamblado del nuevo workspace (rediseño): ViewModels + paneles reales.

Punto de entrada del rediseño. Construye los ViewModels (curva, mapa, batch) sobre un
mismo hub y cablea sus paneles: curva de fuerza (lienzo, inspector, navegador, pipeline),
mapa de propiedades + histograma y tabla de batch. Registra comandos globales (abrir,
calcular mapa, exportar, copiar, navegar). Las perspectivas imagen/figura/simulador
siguen con placeholders hasta su fase de migración.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QFileDialog

from spmkit.core.io import load_force, supported_force_extensions
from spmkit.gui.panels.batch_table import BatchTablePanel
from spmkit.gui.panels.force_canvas import ForceCanvasPanel
from spmkit.gui.panels.histogram_panel import HistogramPanel
from spmkit.gui.panels.inspector import InspectorPanel
from spmkit.gui.panels.map_canvas import MapCanvasPanel
from spmkit.gui.panels.navigator import NavigatorPanel
from spmkit.gui.panels.pipeline_panel import PipelinePanel
from spmkit.gui.shell.command_palette import Command
from spmkit.gui.shell.workspace import Workspace
from spmkit.gui.viewmodels import BatchViewModel, ForceViewModel, MapViewModel


def build_workspace(mode: str = "dark") -> Workspace:
    """Construye el workspace con las perspectivas de curva, mapa y batch cableadas."""
    vm = ForceViewModel()
    map_vm = MapViewModel(vm)
    batch_vm = BatchViewModel(vm)
    panels = {
        "force_canvas": ForceCanvasPanel(vm),
        "inspector": InspectorPanel(vm),
        "navigator": NavigatorPanel(vm),
        "pipeline": PipelinePanel(vm),
        "map_canvas": MapCanvasPanel(map_vm, vm),
        "histogram": HistogramPanel(map_vm),
        "batch_table": BatchTablePanel(batch_vm),
    }
    ws = Workspace(panels=panels, mode=mode)
    map_vm.taskStarted.connect(ws.bind_task)
    batch_vm.taskStarted.connect(ws.bind_task)
    ws.register_command(Command("Abrir curva/volumen…", lambda: _open_dialog(ws, vm), "Ctrl+O"))
    ws.register_command(Command("Calcular mapa de propiedades", map_vm.compute, "Ctrl+M"))
    ws.register_command(
        Command("Exportar resultados (JSON)…", lambda: _export_results(ws, vm), "Ctrl+E")
    )
    ws.register_command(Command("Exportar figura…", lambda: _export_figure(ws, vm)))
    ws.register_command(Command("Copiar resultados", lambda: _copy_results(ws, vm), "Ctrl+Shift+C"))
    ws.register_command(Command("Curva anterior", lambda: vm.set_curve(vm.index - 1), "Ctrl+Left"))
    ws.register_command(
        Command("Curva siguiente", lambda: vm.set_curve(vm.index + 1), "Ctrl+Right")
    )
    ws.register_command(Command("Primera curva", lambda: vm.set_curve(0), "Ctrl+Home"))
    ws.register_command(Command("Última curva", lambda: vm.set_curve(vm.n_curves - 1), "Ctrl+End"))
    return ws


def _scalar_results(ctx: dict) -> dict:
    """Filtra el contexto a valores serializables (descarta el objeto de ajuste)."""
    return {k: v for k, v in ctx.items() if isinstance(v, (int, float, str, bool)) or v is None}


def _results_tsv(ctx: dict) -> str:
    """Serializa los resultados escalares como texto tabulado (para el portapapeles)."""
    return "\n".join(f"{k}\t{v}" for k, v in _scalar_results(ctx).items())


def _copy_results(ws: Workspace, vm: ForceViewModel) -> None:
    ctx = vm.current_results()
    if not ctx:
        ws.show_status("no hay resultados que copiar")
        return
    clipboard = QApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(_results_tsv(ctx))
        ws.show_status("resultados copiados al portapapeles")


def _export_results(ws: Workspace, vm: ForceViewModel) -> None:
    ctx = vm.current_results()
    if not ctx:
        ws.show_status("no hay resultados que exportar (abre una curva y ajusta)")
        return
    path, _ = QFileDialog.getSaveFileName(
        ws, "Exportar resultados", "resultados.json", "JSON (*.json)"
    )
    if not path:
        return
    Path(path).write_text(json.dumps(_scalar_results(ctx), indent=2, ensure_ascii=False))
    ws.show_status(f"resultados exportados a {Path(path).name}")


def _export_figure(ws: Workspace, vm: ForceViewModel) -> None:
    curve = vm.result_curve()
    if curve is None:
        ws.show_status("no hay curva ajustada que exportar")
        return
    path, _ = QFileDialog.getSaveFileName(
        ws, "Exportar figura", "curva.png", "Imagen (*.png *.pdf *.svg)"
    )
    if not path:
        return
    try:
        from spmkit.core.viz import save_force_curve

        save_force_curve(curve, vm.current_results(), path)
    except Exception as exc:  # noqa: BLE001 - falta extra viz o error de IO: se informa
        ws.show_status(f"no se pudo exportar la figura: {exc}")
        return
    ws.show_status(f"figura exportada a {Path(path).name}")


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
