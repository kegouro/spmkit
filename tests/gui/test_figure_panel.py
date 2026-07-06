"""Tests del editor de figuras de Fathom (ViewModel sobre el hub de imagen + panel)."""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel, SPMData
from spmkit.core.viz.figure import Annotation
from spmkit.gui.panels.figure_panel import FigurePanel
from spmkit.gui.viewmodels import FigureViewModel, ImageViewModel


def _data() -> SPMData:
    z = np.tile(np.linspace(0, 1e-8, 48), (48, 1))
    return SPMData(
        channels=(SPMChannel(name="Z-Axis", data=z, unit="m", x_range=1e-6, y_range=1e-6),)
    )


def test_figure_vm_tracks_image_hub_and_edits() -> None:
    image_vm = ImageViewModel()
    vm = FigureViewModel(image_vm)
    changes: list[int] = []
    vm.changed.connect(lambda: changes.append(1))
    image_vm.set_data(_data())
    assert vm.names == ["Z-Axis"]
    assert vm.channel == "Z-Axis"
    assert vm.current_channel() is not None

    vm.update_spec(title="Mi figura", colormap="viridis")
    assert vm.spec.title == "Mi figura" and vm.spec.colormap == "viridis"

    ann = Annotation(text="a", x=0.5, y=0.5)
    vm.add_annotation(ann)
    assert ann in vm.annotations
    vm.remove_annotation(ann)
    assert ann not in vm.annotations


def test_figure_panel_draws_channel(qtbot) -> None:  # type: ignore[no-untyped-def]
    image_vm = ImageViewModel()
    vm = FigureViewModel(image_vm)
    panel = FigurePanel(vm)
    qtbot.addWidget(panel)
    assert not panel.errored
    image_vm.set_data(_data())
    assert panel._canvas.figure.axes  # se renderizó el canal
    assert panel._channel.count() == 1


def test_figure_panel_manual_range(qtbot) -> None:  # type: ignore[no-untyped-def]
    image_vm = ImageViewModel()
    vm = FigureViewModel(image_vm)
    panel = FigurePanel(vm)
    qtbot.addWidget(panel)
    image_vm.set_data(_data())
    panel._auto_range.setChecked(False)
    panel._vmin.setText("0")
    panel._vmax.setText("5")
    panel._push_range()
    assert vm.spec.vmin == 0.0 and vm.spec.vmax == 5.0
