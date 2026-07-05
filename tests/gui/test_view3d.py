"""Tests de la Vista 3D: auto-escala de altura Z a nm/µm (no metros crudos)."""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel, SPMData
from spmkit.gui.view3d_tab import View3DTab, _height_units


def test_height_units_autoscale() -> None:
    assert _height_units("m", np.array([0.0, 5e-8]))[1] == "nm"  # relieve sub-µm → nm
    assert _height_units("m", np.array([0.0, 5e-6]))[1] == "µm"  # relieve mayor → µm
    assert _height_units("V", np.array([0.0, 1.0])) == (1.0, "V")  # no-metros: sin cambio


def test_view3d_zlabel_is_physical(qtbot) -> None:  # type: ignore[no-untyped-def]
    z = np.tile(np.linspace(0, 5e-8, 32), (32, 1))
    data = SPMData(
        channels=(SPMChannel(name="Z-Axis", data=z, unit="m", x_range=1e-6, y_range=1e-6),)
    )
    tab = View3DTab()
    qtbot.addWidget(tab)
    tab.set_data(data)
    assert tab.figure.axes[0].get_zlabel() == "Z (nm)"  # no "Z (m)"
