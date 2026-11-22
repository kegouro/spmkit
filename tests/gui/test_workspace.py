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


def test_persistence_roundtrips_theme_and_perspective(qtbot) -> None:  # type: ignore[no-untyped-def]
    from PyQt6.QtCore import QSettings

    settings = QSettings("spmkit", "spmkit")
    for key in ("theme", "perspective", "geometry"):
        settings.remove(key)  # empezar limpio (namespace propio de la app)
    try:
        ws = Workspace(mode="dark", persist=True)
        qtbot.addWidget(ws)
        ws.toggle_theme()  # → light, persistido
        ws.set_perspective("map")  # persistido
        ws2 = Workspace(mode="dark", persist=True)
        qtbot.addWidget(ws2)
        assert ws2.mode == "light"
        assert ws2.active_perspective == "map"
    finally:
        for key in ("theme", "perspective", "geometry"):
            settings.remove(key)


def test_no_persist_is_default(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = Workspace()  # persist=False por defecto
    qtbot.addWidget(ws)
    assert ws.active_perspective == "force"  # ignora cualquier estado guardado


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


def test_add_toolbar_action_visible(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = Workspace()
    qtbot.addWidget(ws)
    hits: list[int] = []
    ws.add_toolbar_action("📂  Abrir…", lambda: hits.append(1))
    labels = [a.text() for a in ws._file_bar.actions() if a.text()]
    assert "📂  Abrir…" in labels
    assert labels.index("📂  Abrir…") < labels.index("Comandos")
    next(a for a in ws._file_bar.actions() if a.text() == "📂  Abrir…").trigger()
    assert hits == [1]  # el botón dispara el callback


def test_build_workspace_has_open_button(qtbot) -> None:  # type: ignore[no-untyped-def]
    from spmkit.gui.app_workspace import build_workspace

    ws = build_workspace()
    qtbot.addWidget(ws)
    labels = [a.text() for a in ws._file_bar.actions() if a.text()]
    assert any("Abrir" in t for t in labels) and any("Guardar" in t for t in labels)


def test_guide_tracks_controls_and_can_be_replayed(qtbot):
    from PyQt6.QtCore import QPoint, Qt

    from spmkit.gui.app_workspace import build_workspace

    ws = build_workspace()
    qtbot.addWidget(ws)
    ws.resize(1024, 768)
    ws.show()
    qtbot.waitExposed(ws)
    ws._guide_action.trigger()
    guide = ws._guide
    assert guide.isVisible()
    target = ws._file_bar.widgetForAction(ws._open_action)
    assert guide._outline.geometry().topLeft() == target.mapTo(ws, QPoint())
    guide._next.click()
    assert guide._outline.size() == ws._persp_bar.size()
    guide._back.click()
    assert guide._title.text() == "Abre una adquisición"
    for _ in range(4):
        guide._next.click()
    assert not guide.isVisible() and not guide._outline.isVisible()
    ws.open_guide()
    qtbot.keyClick(guide._next, Qt.Key.Key_Escape)
    assert not guide.isVisible()
    assert ws.active_perspective == "force"


def test_force_theme_preserves_axis_units_and_view(qtbot):
    from spmkit.gui.app_workspace import build_workspace
    from spmkit.gui.design import tokens
    from spmkit.gui.design.appearance import Appearance

    ws = build_workspace()
    qtbot.addWidget(ws)
    canvas = ws.panel("force_canvas")
    canvas._plot.setXRange(10, 20, padding=0)
    before = canvas._plot.viewRange()[0]
    ws.set_appearance(Appearance(theme="light"))
    axis = canvas._resid.getAxis("bottom")
    assert (axis.labelText, axis.labelUnits) == ("Separación", "nm")
    assert canvas._plot.viewRange()[0] == before
    assert canvas._extend_item.opts["pen"].color().name().upper() == tokens.LIGHT_TRACES["extend"]
