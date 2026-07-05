"""Smoke tests de los paneles de la perspectiva de mapa (imagen + histograma)."""

from __future__ import annotations

from spmkit.gui.panels.histogram_panel import HistogramPanel
from spmkit.gui.panels.map_canvas import MapCanvasPanel
from spmkit.gui.viewmodels import ForceViewModel, MapViewModel


def test_map_canvas_draws_and_links(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    mvm = MapViewModel(fvm)
    panel = MapCanvasPanel(mvm, fvm)
    qtbot.addWidget(panel)
    assert not panel.errored
    assert panel._selector.count() == len(mvm.keys)
    fvm.set_volume(synthetic_volume(6))
    mvm.compute_now()
    assert panel._image.image is not None
    assert panel._image.image.shape == (1, 6)
    # Linked brushing curva → mapa: la cruz sigue a la curva activa.
    fvm.set_curve(4)
    assert panel._target.isVisible()


def test_map_engine_selector_reflects_backends(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    mvm = MapViewModel(fvm)
    panel = MapCanvasPanel(mvm, fvm)
    qtbot.addWidget(panel)
    values = [panel._engine.itemData(i) for i in range(panel._engine.count())]
    assert "fast_cpu" in values
    assert "pipeline" in values
    # Sin GPU CUDA en este equipo, el motor GPU no debe aparecer.
    from spmkit.core import compute

    if "gpu" not in compute.available_backends():
        assert "fast_gpu" not in values


def test_map_colormap_selector(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    mvm = MapViewModel(fvm)
    panel = MapCanvasPanel(mvm, fvm)
    qtbot.addWidget(panel)
    assert panel._cmap.count() >= 4  # varias paletas disponibles
    panel._cmap.setCurrentText("viridis")  # dispara _apply_colormap
    panel._cmap.setCurrentText("gold")
    assert not panel.errored


def test_map_canvas_click_selects_curve(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    mvm = MapViewModel(fvm)
    panel = MapCanvasPanel(mvm, fvm)
    qtbot.addWidget(panel)
    fvm.set_volume(synthetic_volume(5))
    mvm.compute_now()
    # Selección vía la VM (equivale a clic en el píxel): mueve la curva compartida.
    mvm.select(3)
    assert fvm.index == 3


def test_histogram_updates_with_map(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    mvm = MapViewModel(fvm)
    panel = HistogramPanel(mvm)
    qtbot.addWidget(panel)
    assert not panel.errored
    fvm.set_volume(synthetic_volume(8))
    mvm.compute_now()
    x, y = panel._bars.getData()
    assert x is not None and len(x) > 0
    assert panel._stats.text() != "—"
