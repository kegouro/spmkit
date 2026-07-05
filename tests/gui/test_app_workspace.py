"""Test de ensamblado del workspace del rediseño (paneles reales cableados)."""

from __future__ import annotations

from spmkit.gui.app_workspace import _results_tsv, _scalar_results, build_workspace
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
    assert any("Exportar" in t for t in titles)


def test_scalar_results_drops_nonserializable() -> None:
    ctx = {"young_modulus": 1e6, "model": "sphere", "fit": object(), "ok": True, "none": None}
    out = _scalar_results(ctx)
    assert out == {"young_modulus": 1e6, "model": "sphere", "ok": True, "none": None}
    assert "fit" not in out


def test_results_tsv_serializes_scalars() -> None:
    tsv = _results_tsv({"young_modulus": 1e6, "fit": object(), "model": "sphere"})
    assert "young_modulus\t1000000.0" in tsv
    assert "model\tsphere" in tsv
    assert "fit" not in tsv


def test_navigation_and_copy_commands_registered(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = build_workspace()
    qtbot.addWidget(ws)
    titles = [c.title for c in ws._commands]
    assert "Curva siguiente" in titles
    assert "Curva anterior" in titles
    assert "Copiar resultados" in titles


def test_map_perspective_switches(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = build_workspace()
    qtbot.addWidget(ws)
    ws.set_perspective("map")
    assert ws.active_perspective == "map"
    assert ws.visible_docks() == {"navigator", "inspector", "histogram"}
