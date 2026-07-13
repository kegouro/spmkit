"""Ensamblado del nuevo workspace (rediseño): ViewModels + paneles reales.

Punto de entrada del rediseño. Construye los ViewModels (curva, mapa, batch) sobre un
mismo hub y cablea sus paneles: curva de fuerza (lienzo, inspector, navegador, pipeline),
mapa de propiedades + histograma y tabla de batch. Registra comandos globales (abrir,
calcular mapa, exportar, copiar, navegar). Imagen, figura, vista 3D y simulador comparten
el hub de imagen y ya son paneles reales (perspectivas MVVM, no placeholders).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from spmkit.core.plugins.contracts import DatasetInfo, Kind
from spmkit.gui.design import brand
from spmkit.gui.extensions import ModuleContext, assemble, iter_modules
from spmkit.gui.shell.command_palette import Command
from spmkit.gui.shell.workspace import Workspace
from spmkit.gui.viewmodels import (
    BatchViewModel,
    ForceViewModel,
    ImageViewModel,
    MapViewModel,
)


def build_workspace(
    mode: str = "dark", open_path: str | Path | None = None, persist: bool = False
) -> Workspace:
    """Construye el workspace con las perspectivas de curva, mapa y batch cableadas.

    Si se pasa ``open_path``, carga ese archivo de curvas al arrancar. ``persist`` guarda
    tema/geometría/perspectiva entre sesiones (activo en la app real, no en los tests).
    """
    # Hubs compartidos (curva/mapa/batch e imagen); los módulos cablean sus paneles a ellos.
    vm = ForceViewModel()
    map_vm = MapViewModel(vm)
    batch_vm = BatchViewModel(vm)
    image_vm = ImageViewModel()
    ctx = ModuleContext(force_vm=vm, image_vm=image_vm, map_vm=map_vm, batch_vm=batch_vm)

    # La app se ensambla desde los módulos (fábrica + descubiertos por entry-point): añadir
    # un módulo aporta sus paneles y perspectivas sin tocar la shell (ver gui/extensions.py).
    modules = iter_modules()
    layout = assemble(modules, ctx)
    ws = Workspace(
        panels=layout.panels,
        mode=mode,
        persist=persist,
        perspectives=layout.perspectives,
        panel_labels=layout.panel_labels,
        dock_areas=layout.dock_areas,
        central_panels=layout.central_panels,
    )
    ws.setWindowTitle(brand.WINDOW_TITLE)
    icon = _brand_icon()
    if icon is not None:
        ws.setWindowIcon(icon)
    for module in modules:  # cada módulo conecta sus señales a la shell (estado/progreso)
        if module.wire is not None:
            module.wire(ws, ctx)
    session = ctx.session  # último archivo abierto (para .spmproj)
    force_canvas = ctx.store["force_canvas"]  # para los comandos fijar/limpiar
    ws.fileDropped.connect(lambda p: _load_into(ws, vm, image_vm, p, session))
    ws.register_command(
        Command("Abrir curva o imagen…", lambda: _open_dialog(ws, vm, image_vm, session), "Ctrl+O")
    )
    ws.register_command(
        Command("Guardar proyecto…", lambda: _save_project(ws, vm, session), "Ctrl+S")
    )
    ws.register_command(
        Command("Abrir proyecto…", lambda: _open_project(ws, vm, image_vm, session))
    )
    ws.register_command(Command("Calcular mapa de propiedades", map_vm.compute, "Ctrl+M"))
    ws.register_command(
        Command("Exportar resultados (JSON)…", lambda: _export_results(ws, vm), "Ctrl+E")
    )
    ws.register_command(Command("Exportar figura…", lambda: _export_figure(ws, vm)))
    ws.register_command(
        Command("Generar informe (HTML/PDF)…", lambda: _generate_report(ws, vm), "Ctrl+Shift+R")
    )
    ws.register_command(Command("Exportar todo…", lambda: _export_all(ws, vm)))
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
    ws.register_command(Command(f"Acerca de {brand.PRODUCT_NAME}", lambda: _about(ws)))
    # Botones visibles de archivo (el drag & drop es incómodo en laptops; el explorador de
    # archivos permite escribir/pegar una ruta). Sin atajo aquí: los comandos ya tienen Ctrl+O/S.
    ws.add_toolbar_action("📂  Abrir…", lambda: _open_dialog(ws, vm, image_vm, session))
    ws.add_toolbar_action("💾  Guardar…", lambda: _save_project(ws, vm, session))
    ws.add_toolbar_separator()
    if open_path is not None:
        _load_into(ws, vm, image_vm, open_path, session)
    return ws


def _choose_kind(ws: Workspace, info: DatasetInfo) -> Kind | None:
    """Si el archivo declara varios ``kinds``, pregunta cuál abrir; si no, el único."""
    if len(info.kinds) <= 1:
        return info.kinds[0] if info.kinds else None
    box = QMessageBox(ws)
    box.setWindowTitle("Abrir como…")
    box.setText(f"{info.path.name} contiene imagen y curvas de fuerza. ¿Cómo abrirlo?")
    img_btn = box.addButton("Imagen", QMessageBox.ButtonRole.AcceptRole)
    force_btn = box.addButton("Mapa de curvas", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    clicked = box.clickedButton()
    if clicked is img_btn:
        return "image"
    if clicked is force_btn:
        return "force"
    return None


def _load_into(
    ws: Workspace,
    vm: ForceViewModel,
    image_vm: ImageViewModel,
    path: str | Path,
    session: dict[str, Any] | None = None,
    kind_hint: Kind | None = None,
) -> None:
    """Abre ``path`` por capacidades (``inspect_any``/``load_any``) y rutea a la perspectiva."""
    from spmkit.core.io import inspect_any, load_any

    name = Path(path).name
    try:
        info = inspect_any(path)
    except Exception as exc:  # noqa: BLE001 - formato no soportado / error IO: se informa
        ws.show_status(f"No se pudo abrir {name}: {exc}")
        return
    kind = kind_hint or _choose_kind(ws, info)
    if kind is None:
        return  # cancelado
    try:
        data, kind = load_any(path, kind)
    except Exception as exc:  # noqa: BLE001 - error de carga: se informa, no tumba
        ws.show_status(f"No se pudo abrir {name}: {exc}")
        return
    _remember_dir(str(path))
    if session is not None:
        session["path"], session["kind"] = str(path), kind
    if kind == "force":
        vm.set_volume(data)
        ws.set_perspective("force")
        ws.show_status(f"{name} — {vm.n_curves} curva(s)")
    else:
        image_vm.set_data(data)
        ws.set_perspective("image")
        ws.show_status(f"{name} — imagen ({len(image_vm.names)} canales)")


def _save_project(ws: Workspace, vm: ForceViewModel, session: dict[str, Any]) -> None:
    """Guarda un ``.spmproj``: archivo abierto + parámetros + perspectiva."""
    from spmkit.core.project import OpenFile, ProjectState, save_project

    path, _ = QFileDialog.getSaveFileName(
        ws, "Guardar proyecto", _suggested("sesion.spmproj"), "Proyecto spmkit (*.spmproj)"
    )
    if not path:
        return
    without_hash = False
    files = []
    if session.get("path"):
        try:
            files = [OpenFile.from_path(session["path"], session["kind"])]
        except OSError:
            files = [OpenFile(path=str(session["path"]), kind=session["kind"], sha256=None)]
            without_hash = True
    state = ProjectState(files=files, params=vm.params, perspective=ws.active_perspective)
    save_project(state, path)
    _remember_dir(path)
    if without_hash:
        ws.show_status(
            f"proyecto guardado sin hash: {Path(path).name}; "
            "restaura el archivo de origen y vuelve a guardar"
        )
    else:
        ws.show_status(f"proyecto guardado: {Path(path).name}")


def _open_project(
    ws: Workspace, vm: ForceViewModel, image_vm: ImageViewModel, session: dict[str, Any]
) -> None:
    """Abre un ``.spmproj``: reabre el archivo, aplica parámetros y perspectiva."""
    from spmkit.core.project import load_project

    path, _ = QFileDialog.getOpenFileName(
        ws, "Abrir proyecto", _last_dir(), "Proyecto spmkit (*.spmproj)"
    )
    if not path:
        return
    try:
        state = load_project(path)
    except Exception as exc:  # noqa: BLE001 - .spmproj corrupto: se informa
        ws.show_status(f"no se pudo abrir el proyecto: {exc}")
        return
    if state.params:
        vm.set_params(**state.params)
    for f in state.files:
        if Path(f.path).exists():
            _load_into(ws, vm, image_vm, f.path, session, kind_hint=f.kind)  # type: ignore[arg-type]
        else:
            ws.show_status(f"archivo del proyecto no encontrado: {Path(f.path).name}")
    if state.perspective:
        ws.set_perspective(state.perspective)


def _brand_icon() -> QIcon | None:
    """Construye un ``QIcon`` del logo-símbolo (SVG embebido); ``None`` si falta QtSvg."""
    try:
        from PyQt6.QtCore import QByteArray, Qt
        from PyQt6.QtGui import QImage, QPainter, QPixmap
        from PyQt6.QtSvg import QSvgRenderer
    except ImportError:  # pragma: no cover - QtSvg es parte de PyQt6, casi siempre está
        return None
    renderer = QSvgRenderer(QByteArray(brand.MARK_SVG.encode()))
    image = QImage(128, 128, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QIcon(QPixmap.fromImage(image))


def _about(ws: Workspace) -> None:
    """Diálogo 'Acerca de' con la identidad del producto."""
    box = QMessageBox(ws)
    box.setWindowTitle(f"Acerca de {brand.PRODUCT_NAME}")
    box.setText(
        f"<h2 style='margin:0'>{brand.PRODUCT_NAME}</h2>"
        f"<p style='color:#93A0AE;margin:4px 0'>{brand.TAGLINE_ES}</p>"
        f"<p style='margin:8px 0'>{brand.DESCRIPTION}</p>"
        f"<p style='color:#93A0AE;margin:0'>{brand.BYLINE}</p>"
    )
    box.exec()


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
    return {k: v for k, v in ctx.items() if isinstance(v, int | float | str | bool) or v is None}


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


def _generate_report(ws: Workspace, vm: ForceViewModel) -> None:
    """Genera un informe magistral (HTML + PDF) del force-volume activo, en un hilo."""
    volume = vm.volume
    if volume is None:
        ws.show_status("no hay force-volume cargado para el informe")
        return
    path, _ = QFileDialog.getSaveFileName(
        ws, "Guardar informe", _suggested("informe.pdf"), "PDF (*.pdf);;HTML (*.html)"
    )
    if not path:
        return
    from spmkit.core.forcereport import build_force_report
    from spmkit.gui.runtime.tasks import Task, run_task

    base = str(Path(path).with_suffix(""))
    formats = ("html",) if Path(path).suffix.lower() == ".html" else ("html", "pdf")
    p = vm.params
    _remember_dir(path)

    def _work() -> dict:
        return build_force_report(
            volume,
            base,
            source_name=Path(base).name,
            model=p["model"],
            tip_radius=p["tip_radius"],
            poisson=p["poisson"],
            formats=formats,
        )

    task = Task(_work)
    task.signals.done.connect(
        lambda produced: ws.show_status(f"informe generado: {', '.join(sorted(produced))}")
    )
    task.signals.error.connect(lambda exc: ws.show_status(f"informe falló: {exc}"))
    ws.bind_task(task)
    ws.show_status("generando informe…")
    run_task(task)


def _export_all(ws: Workspace, vm: ForceViewModel) -> None:
    """Exporta todo el force-volume (mapas CSV, tabla, resumen, informe) a una carpeta."""
    volume = vm.volume
    if volume is None:
        ws.show_status("no hay force-volume cargado para exportar")
        return
    folder = QFileDialog.getExistingDirectory(ws, "Carpeta para exportar todo", _last_dir())
    if not folder:
        return
    from spmkit.core.forceexport import export_bundle
    from spmkit.gui.runtime.tasks import Task, run_task

    p = vm.params
    _remember_dir(folder)

    def _work() -> dict:
        return export_bundle(
            volume,
            folder,
            source_name=Path(folder).name,
            model=p["model"],
            tip_radius=p["tip_radius"],
            poisson=p["poisson"],
        )

    task = Task(_work)
    task.signals.done.connect(
        lambda m: ws.show_status(f"exportados {len(m)} archivos a {Path(folder).name}")
    )
    task.signals.error.connect(lambda exc: ws.show_status(f"exportación falló: {exc}"))
    ws.bind_task(task)
    ws.show_status("exportando todo…")
    run_task(task)


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


def _open_dialog(
    ws: Workspace, vm: ForceViewModel, image_vm: ImageViewModel, session: dict[str, Any]
) -> None:
    from spmkit.core.plugins import supported_extensions

    globs = " ".join(f"*{e}" for e in supported_extensions())
    path, _ = QFileDialog.getOpenFileName(
        ws, "Abrir datos SPM", _last_dir(), f"Datos SPM ({globs})"
    )
    if path:
        _load_into(ws, vm, image_vm, path, session)


def run(open_path: str | Path | None = None) -> int:
    """Lanza el workspace del rediseño como app independiente (abre ``open_path`` si se da)."""
    app = QApplication.instance() or QApplication(sys.argv)
    ws = build_workspace(open_path=open_path, persist=True)
    ws.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
