"""Test de ensamblado del workspace del rediseño (paneles reales cableados)."""

from __future__ import annotations

from spmkit.gui.app_workspace import build_workspace
from spmkit.gui.panels.force_canvas import ForceCanvasPanel


def test_build_workspace_wires_force_panels(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = build_workspace()
    qtbot.addWidget(ws)
    assert ws.active_perspective == "force"
    assert isinstance(ws.panel("force_canvas"), ForceCanvasPanel)
    titles = [c.title for c in ws._commands]
    assert any("Abrir" in t for t in titles)
