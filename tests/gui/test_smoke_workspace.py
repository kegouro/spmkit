"""Smoke test integral del workspace Fathom: recorre todo y verifica que nada crashea.

Carga datos, cambia por todas las perspectivas, ejercita cada panel (mapa CPU/GPU,
región, indentación, fijar, batch) y ejecuta **todos** los comandos con los diálogos
bloqueantes neutralizados. Al final, ningún panel debe estar en estado de error.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from spmkit.gui.app_workspace import build_workspace
from spmkit.gui.shell.perspectives import ALL_PANELS, PERSPECTIVES


def _silence_dialogs(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)


def test_full_workspace_smoke(qtbot, synthetic_volume, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _silence_dialogs(monkeypatch)
    ws = build_workspace()
    qtbot.addWidget(ws)

    # Cargar un force-volume en el hub de fuerza.
    canvas = ws.panel("force_canvas")
    vm = canvas._vm
    vm.set_volume(synthetic_volume(9))
    vm.run_fit_now()

    # Recorrer todas las perspectivas.
    for persp in PERSPECTIVES:
        ws.set_perspective(persp.key)
        assert ws.active_perspective == persp.key

    # Ejercitar el mapa con ambos motores + pop-up de info.
    ws.set_perspective("map")
    map_panel = ws.panel("map_canvas")
    map_panel._vm.compute_now("fast_cpu")
    map_panel._vm.compute_now("pipeline")
    map_panel._show_engine_info()
    map_panel._vm.select(3)
    assert vm.index == 3

    # Ejercitar el lienzo de fuerza: fijar, región, modo indentación.
    ws.set_perspective("force")
    canvas.pin_current()
    canvas._region_check.setChecked(True)
    canvas._region_check.setChecked(False)
    canvas._axis_mode.setCurrentIndex(canvas._axis_mode.findData("ind"))
    canvas._axis_mode.setCurrentIndex(canvas._axis_mode.findData("sep"))

    # Editar el pipeline en vivo (dispara re-ajuste con debounce).
    pipe = ws.panel("pipeline")
    pipe._model.setCurrentIndex(pipe._model.findData("dmt"))
    pipe._smooth.setValue(11)
    pipe._smooth.setValue(0)

    # Ejecutar TODOS los comandos (diálogos neutralizados) — ninguno debe lanzar.
    for command in ws._commands:
        command.callback()

    qtbot.wait(200)  # dejar terminar tareas asíncronas lanzadas por comandos

    # Ningún panel quedó en estado de error.
    for key in ALL_PANELS:
        panel = ws.panel(key)
        assert panel is None or not panel.errored, f"panel «{key}» quedó en error"
