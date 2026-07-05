"""Test de ensamblado del workspace del rediseño (paneles reales cableados)."""

from __future__ import annotations

from spmkit.gui.app_workspace import build_workspace
from spmkit.gui.panels.force_canvas import ForceCanvasPanel
from spmkit.gui.panels.map_canvas import MapCanvasPanel


def test_build_workspace_wires_force_and_map_panels(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = build_workspace()
    qtbot.addWidget(ws)
    assert ws.active_perspective == "force"
    assert isinstance(ws.panel("force_canvas"), ForceCanvasPanel)
    assert isinstance(ws.panel("map_canvas"), MapCanvasPanel)
    titles = [c.title for c in ws._commands]
    assert any("Abrir" in t for t in titles)
    assert any("mapa" in t.lower() for t in titles)


def test_map_perspective_switches(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = build_workspace()
    qtbot.addWidget(ws)
    ws.set_perspective("map")
    assert ws.active_perspective == "map"
    assert ws.visible_docks() == {"navigator", "inspector", "histogram"}
