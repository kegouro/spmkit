"""Tests del Workspace y la paleta de comandos (pytest-qt)."""

from __future__ import annotations

from spmkit.gui.shell.command_palette import Command, CommandPalette
from spmkit.gui.shell.workspace import Workspace


def test_workspace_builds_with_default_perspective(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = Workspace()
    qtbot.addWidget(ws)
    assert ws.active_perspective == "force"
    # La perspectiva de curva de fuerza muestra navegador, inspector y pipeline.
    assert ws.visible_docks() == {"navigator", "inspector", "pipeline"}


def test_switch_perspective_updates_docks(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = Workspace()
    qtbot.addWidget(ws)
    ws.set_perspective("map")
    assert ws.active_perspective == "map"
    assert ws.visible_docks() == {"navigator", "inspector", "histogram"}
    ws.set_perspective("simulator")
    assert ws.visible_docks() == set()  # el simulador no usa docks


def test_toggle_theme_flips_mode(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = Workspace(mode="dark")
    qtbot.addWidget(ws)
    ws.toggle_theme()
    assert ws.mode == "light"
    ws.toggle_theme()
    assert ws.mode == "dark"


def test_command_palette_filters_and_runs(qtbot) -> None:  # type: ignore[no-untyped-def]
    ran = {"ok": False}
    commands = [
        Command("Ajustar elasticidad", lambda: ran.__setitem__("ok", True)),
        Command("Calibrar cantilever", lambda: None),
        Command("Exportar figura", lambda: None),
    ]
    palette = CommandPalette(commands)
    qtbot.addWidget(palette)

    palette._filter("ajust")
    assert palette.visible_titles() == ["Ajustar elasticidad"]

    palette._filter("")
    assert len(palette.visible_titles()) == 3

    palette._filter("cali")
    palette._run_current()
    assert ran["ok"] is False  # corrió "Calibrar", no "Ajustar"


def test_command_palette_runs_selected(qtbot) -> None:  # type: ignore[no-untyped-def]
    hits: list[str] = []
    commands = [Command("Ir a Mapa", lambda: hits.append("mapa"))]
    palette = CommandPalette(commands)
    qtbot.addWidget(palette)
    palette._filter("mapa")
    palette._run_current()
    assert hits == ["mapa"]
