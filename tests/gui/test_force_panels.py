"""Smoke tests de los paneles de la perspectiva de curva de fuerza."""

from __future__ import annotations

from spmkit.gui.panels.force_canvas import ForceCanvasPanel
from spmkit.gui.panels.inspector import InspectorPanel
from spmkit.gui.panels.navigator import NavigatorPanel
from spmkit.gui.viewmodels import ForceViewModel


def test_canvas_renders_and_overlays_fit(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = ForceCanvasPanel(vm)
    qtbot.addWidget(panel)
    assert not panel.errored  # pyqtgraph disponible, build() no falló
    vm.set_volume(synthetic_volume(3))
    vm.run_fit_now()
    x, y = panel._fit_item.getData()
    assert x is not None and len(x) > 0  # la línea de ajuste se dibujó
    assert panel._contact_line.isVisible()


def test_canvas_scrubber_tracks_volume(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = ForceCanvasPanel(vm)
    qtbot.addWidget(panel)
    vm.set_volume(synthetic_volume(5))
    assert panel._scrubber.maximum() == 4
    panel._scrubber.setValue(3)
    assert vm.index == 3


def test_inspector_shows_modulus(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = InspectorPanel(vm)
    qtbot.addWidget(panel)
    vm.set_volume(synthetic_volume(1))
    vm.run_fit_now()
    assert not panel.errored
    assert panel._values["young"].text() != "—"
    assert panel._values["r_squared"].text() != "—"


def test_navigator_lists_and_steps(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = NavigatorPanel(vm)
    qtbot.addWidget(panel)
    vm.set_volume(synthetic_volume(4))
    assert panel._list.count() == 4
    panel._step(1)
    assert vm.index == 1
    assert panel._list.currentRow() == 1
