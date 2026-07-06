"""Tests de la vista 3D de Fathom (ViewModel sobre el hub de imagen + panel)."""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel, SPMData
from spmkit.gui.panels.view3d_panel import View3DPanel, _height_units
from spmkit.gui.viewmodels import ImageViewModel, View3DViewModel


def _data() -> SPMData:
    z = np.tile(np.linspace(0, 5e-8, 32), (32, 1))
    return SPMData(
        channels=(
            SPMChannel(name="Deflection", data=z * 2, unit="m", x_range=1e-6, y_range=1e-6),
            SPMChannel(name="Z-Axis", data=z, unit="m", x_range=1e-6, y_range=1e-6),
        )
    )


def test_height_units_autoscale() -> None:
    assert _height_units("m", np.array([0.0, 5e-8]))[1] == "nm"
    assert _height_units("m", np.array([0.0, 5e-6]))[1] == "µm"
    assert _height_units("V", np.array([0.0, 1.0])) == (1.0, "V")


def test_view3d_vm_prefers_z_axis_and_reacts() -> None:
    image_vm = ImageViewModel()
    vm = View3DViewModel(image_vm)
    changes: list[int] = []
    vm.changed.connect(lambda: changes.append(1))
    image_vm.set_data(_data())
    assert vm.channel == "Z-Axis"  # prefiere el canal de altura, no el primero
    assert vm.current_channel() is not None
    before = len(changes)
    vm.set_z_exag(200)
    assert vm.z_exag == 200 and len(changes) == before + 1


def test_view3d_panel_zlabel_is_physical(qtbot) -> None:  # type: ignore[no-untyped-def]
    image_vm = ImageViewModel()
    vm = View3DViewModel(image_vm)
    panel = View3DPanel(vm)
    qtbot.addWidget(panel)
    assert not panel.errored
    image_vm.set_data(_data())
    assert panel._figure.axes[0].get_zlabel() == "Z (nm)"  # físico, no "Z (m)"
