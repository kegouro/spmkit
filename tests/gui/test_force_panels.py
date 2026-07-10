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


def test_canvas_residuals_and_indentation_mode(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = ForceCanvasPanel(vm)
    qtbot.addWidget(panel)
    vm.set_volume(synthetic_volume(1))
    vm.run_fit_now()
    rx, ry = panel._resid_item.getData()
    assert rx is not None and len(rx) > 0  # la tira de residuos se dibujó
    # En modo indentación el contacto queda en el origen (~0 nm).
    panel._axis_mode.setCurrentIndex(panel._axis_mode.findData("ind"))
    assert abs(panel._contact_line.value()) < 1e-6


def test_canvas_region_sets_fit_window(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = ForceCanvasPanel(vm)
    qtbot.addWidget(panel)
    vm.set_volume(synthetic_volume(1))
    vm.run_fit_now()
    panel._region_check.setChecked(True)
    assert panel._region.isVisible()
    assert not panel._axis_mode.isEnabled()  # región fuerza modo separación
    assert vm.params["fit_min"] is not None and vm.params["fit_max"] is not None
    panel._region_check.setChecked(False)
    assert vm.params["fit_min"] is None
    assert panel._axis_mode.isEnabled()


def test_canvas_scrubber_tracks_volume(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = ForceCanvasPanel(vm)
    qtbot.addWidget(panel)
    vm.set_volume(synthetic_volume(5))
    assert panel._scrubber.maximum() == 4
    panel._scrubber.setValue(3)
    assert vm.index == 3


def test_canvas_pin_and_clear_curves(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = ForceCanvasPanel(vm)
    qtbot.addWidget(panel)
    vm.set_volume(synthetic_volume(3))
    panel.pin_current()
    vm.set_curve(1)
    panel.pin_current()
    assert len(panel._pinned) == 2
    panel.clear_pinned()
    assert panel._pinned == []


def test_inspector_shows_modulus(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = InspectorPanel(vm)
    qtbot.addWidget(panel)
    vm.set_volume(synthetic_volume(1))
    vm.run_fit_now()
    assert not panel.errored
    assert panel._values["young"].text() != "—"
    assert panel._values["r_squared"].text() != "—"
    assert panel._values["max_force"].text() != "—"
    assert panel._values["max_indentation"].text() != "—"


def test_navigator_lists_and_steps(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    from spmkit.gui.viewmodels import ImageViewModel

    vm = ForceViewModel()
    panel = NavigatorPanel(vm, ImageViewModel())
    qtbot.addWidget(panel)
    vm.set_volume(synthetic_volume(4))
    assert panel._list.count() == 4
    panel._step(1)
    assert vm.index == 1
    assert panel._list.currentRow() == 1


def test_navigator_dual_hub_lists_image_channels(qtbot) -> None:  # type: ignore[no-untyped-def]
    import numpy as np

    from spmkit.core.models import SPMChannel, SPMData
    from spmkit.gui.viewmodels import ImageViewModel

    image_vm = ImageViewModel()
    panel = NavigatorPanel(ForceViewModel(), image_vm)
    qtbot.addWidget(panel)
    z = np.zeros((8, 8))
    image_vm.set_data(
        SPMData(
            channels=(
                SPMChannel(name="Z", data=z, unit="m", x_range=1e-6, y_range=1e-6),
                SPMChannel(name="Phase", data=z, unit="deg", x_range=1e-6, y_range=1e-6),
            )
        )
    )
    assert panel._list.count() == 2  # sin curvas de fuerza → lista canales de imagen
    panel._step(1)  # avanza de canal
    assert image_vm.channel == "Phase"
