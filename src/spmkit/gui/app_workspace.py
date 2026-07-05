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

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QFileDialog

from spmkit.core.io import load_force, supported_force_extensions
from spmkit.gui.panels.batch_table import BatchTablePanel
from spmkit.gui.panels.force_canvas import ForceCanvasPanel
from spmkit.gui.panels.histogram_panel import HistogramPanel
from spmkit.gui.panels.inspector import InspectorPanel
from spmkit.gui.panels.log_panel import LogPanel
from spmkit.gui.panels.map_canvas import MapCanvasPanel
from spmkit.gui.panels.navigator import NavigatorPanel
from spmkit.gui.panels.pipeline_panel import PipelinePanel
from spmkit.gui.shell.command_palette import Command
from spmkit.gui.shell.workspace import Workspace
from spmkit.gui.viewmodels import BatchViewModel, ForceViewModel, MapViewModel


def build_workspace(
    mode: str = "dark", open_path: str | Path | None = None, persist: bool = False
) -> Workspace:
    """Construye el workspace con las perspectivas de curva, mapa y batch cableadas.

    Si se pasa ``open_path``, carga ese archivo de curvas al arrancar. ``persist`` guarda
    tema/geometría/perspectiva entre sesiones (activo en la app real, no en los tests).
    """
    vm = ForceViewModel()
    map_vm = MapViewModel(vm)
    batch_vm = BatchViewModel(vm)
    force_canvas = ForceCanvasPanel(vm)
    panels = {
        "force_canvas": force_canvas,
        "inspector": InspectorPanel(vm),
        "navigator": NavigatorPanel(vm),
        "pipeline": PipelinePanel(vm),
        "map_canvas": MapCanvasPanel(map_vm, vm),
        "histogram": HistogramPanel(map_vm),
        "batch_table": BatchTablePanel(batch_vm),
        "log": LogPanel((vm, map_vm, batch_vm)),
    }
    ws = Workspace(panels=panels, mode=mode, persist=persist)
    map_vm.taskStarted.connect(ws.bind_task)
    batch_vm.taskStarted.connect(ws.bind_task)
    ws.register_command(Command("Abrir curva/volumen…", lambda: _open_dialog(ws, vm), "Ctrl+O"))
    ws.register_command(Command("Calcular mapa de propiedades", map_vm.compute, "Ctrl+M"))
    ws.register_command(
        Command("Exportar resultados (JSON)…", lambda: _export_results(ws, vm), "Ctrl+E")
    )
    ws.register_command(Command("Exportar figura…", lambda: _export_figure(ws, vm)))
    ws.register_command(Command("Exportar mapa (figura)…", lambda: _export_map_figure(ws, map_vm)))
    ws.register_command(Command("Exportar mapa (CSV)…", lambda: _export_map_csv(ws, map_vm)))
    ws.register_command(Command("Copiar resultados", lambda: _copy_results(ws, vm), "Ctrl+Shift+C"))
    ws.register_command(Command("Fijar curva actual", force_canvas.pin_current, "Ctrl+P"))
    ws.register_command(Command("Limpiar curvas fijadas", force_canvas.clear_pinned))
    ws.register_command(Command("Curva anterior", lambda: vm.set_curve(vm.index - 1), "Ctrl+Left"))
    ws.register_command(
        Command("Curva siguiente", lambda: vm.set_curve(vm.index + 1), "Ctrl+Right")
    )
    ws.register_command(Command("Primera curva", lambda: vm.set_curve(0), "Ctrl+Home"))
    ws.register_command(Command("Última curva", lambda: vm.set_curve(vm.n_curves - 1), "Ctrl+End"))
    if open_path is not None:
        _load_into(ws, vm, open_path)
    return ws


def _load_into(ws: Workspace, vm: ForceViewModel, path: str | Path) -> None:
    """Carga un archivo de curvas en el ViewModel (usado al arrancar y desde el diálogo)."""
    try:
        vm.set_volume(load_force(path))
    except Exception as exc:  # noqa: BLE001 - error de IO se muestra, no tumba la app
        ws.show_status(f"No se pudo abrir {Path(path).name}: {exc}")
        return
    _remember_dir(str(path))
    ws.set_perspective("force")
    ws.show_status(f"{Path(path).name} — {vm.n_curves} curva(s)")


def _last_dir() -> str:
    """Último directorio usado en los diálogos (persistido con QSettings)."""
    return str(QSettings("spmkit", "spmkit").value("last_dir", "") or "")


def _remember_dir(path: str) -> None:
    QSettings("spmkit", "spmkit").setValue("last_dir", str(Path(path).parent))


def _suggested(name: str) -> str:
    """Ruta sugerida en un diálogo de guardado: último directorio + nombre por defecto."""
    base = _last_dir()
    return str(Path(base) / name) if base else name


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
        ws, "Exportar resultados", _suggested("resultados.json"), "JSON (*.json)"
    )
    if not path:
        return
    Path(path).write_text(json.dumps(_scalar_results(ctx), indent=2, ensure_ascii=False))
    _remember_dir(path)
    ws.show_status(f"resultados exportados a {Path(path).name}")


def _export_map_figure(ws: Workspace, map_vm: MapViewModel) -> None:
    result = map_vm.result
    if result is None:
        ws.show_status("no hay mapa calculado (calcúlalo primero)")
        return
    path, _ = QFileDialog.getSaveFileName(
        ws, "Exportar mapa", _suggested("mapa.png"), "Imagen (*.png *.pdf)"
    )
    if not path:
        return
    try:
        from spmkit.core.viz.maps import save_property_maps

        save_property_maps(result.maps, path, keys=[map_vm.key])
    except Exception as exc:  # noqa: BLE001 - falta extra viz o mapa vacío: se informa
        ws.show_status(f"no se pudo exportar el mapa: {exc}")
        return
    _remember_dir(path)
    ws.show_status(f"mapa exportado a {Path(path).name}")


def _export_map_csv(ws: Workspace, map_vm: MapViewModel) -> None:
    result = map_vm.result
    if result is None:
        ws.show_status("no hay mapa calculado (calcúlalo primero)")
        return
    path, _ = QFileDialog.getSaveFileName(
        ws, "Exportar mapa CSV", _suggested("mapa.csv"), "CSV (*.csv)"
    )
    if not path:
        return
    import numpy as np

    np.savetxt(path, result.maps[map_vm.key], delimiter=",")
    _remember_dir(path)
    ws.show_status(f"mapa CSV exportado a {Path(path).name}")


def _export_figure(ws: Workspace, vm: ForceViewModel) -> None:
    curve = vm.result_curve()
    if curve is None:
        ws.show_status("no hay curva ajustada que exportar")
        return
    path, _ = QFileDialog.getSaveFileName(
        ws, "Exportar figura", _suggested("curva.png"), "Imagen (*.png *.pdf *.svg)"
    )
    if not path:
        return
    try:
        from spmkit.core.viz import save_force_curve

        save_force_curve(curve, vm.current_results(), path)
    except Exception as exc:  # noqa: BLE001 - falta extra viz o error de IO: se informa
        ws.show_status(f"no se pudo exportar la figura: {exc}")
        return
    _remember_dir(path)
    ws.show_status(f"figura exportada a {Path(path).name}")


def _open_dialog(ws: Workspace, vm: ForceViewModel) -> None:
    exts = " ".join(f"*{e}" for e in supported_force_extensions())
    path, _ = QFileDialog.getOpenFileName(
        ws, "Abrir curva de fuerza", _last_dir(), f"Curvas de fuerza ({exts})"
    )
    if path:
        _load_into(ws, vm, path)


def run(open_path: str | Path | None = None) -> int:
    """Lanza el workspace del rediseño como app independiente (abre ``open_path`` si se da)."""
    app = QApplication.instance() or QApplication(sys.argv)
    ws = build_workspace(open_path=open_path, persist=True)
    ws.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
