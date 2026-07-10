"""Tests de la paridad de imagen en Fathom (F3.1): perfil, nivelado filas, KPFM."""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel, SPMData
from spmkit.gui.panels.image_analysis import ImageAnalysisPanel
from spmkit.gui.panels.image_canvas import ImageCanvasPanel
from spmkit.gui.viewmodels import ImageViewModel


def _height_data() -> SPMData:
    z = np.tile(np.linspace(0, 1e-8, 64), (64, 1))
    return SPMData(
        channels=(SPMChannel(name="Z-Axis", data=z, unit="m", x_range=1e-6, y_range=1e-6),)
    )


def _potential_data() -> SPMData:
    v = np.tile(np.linspace(-0.1, 0.1, 32), (32, 1))
    return SPMData(channels=(SPMChannel(name="CPD", data=v, unit="V", x_range=1e-6, y_range=1e-6),))


def test_vm_profile_emits_and_records() -> None:
    vm = ImageViewModel()
    vm.set_data(_height_data())
    seen: list[object] = []
    vm.profileChanged.connect(seen.append)
    prof = vm.profile((5, 5), (50, 50))
    assert prof is not None and len(prof) > 1
    assert vm.last_profile is prof
    assert seen and seen[-1] is prof


def test_vm_rows_leveling_and_kpfm() -> None:
    vm = ImageViewModel()
    vm.set_data(_height_data())
    vm.set_leveling("rows")
    ch = vm.current_channel()
    assert ch is not None and ch.data.shape == (64, 64)  # align_rows no rompe la forma
    assert vm.kpfm() is None  # canal de altura → sin KPFM

    vm.set_data(_potential_data())
    assert vm.kpfm() is not None  # canal de potencial (V) → CPD


def test_image_canvas_has_colormap_and_rows(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = ImageViewModel()
    panel = ImageCanvasPanel(vm)
    qtbot.addWidget(panel)
    assert not panel.errored
    assert panel._cmap.count() >= 4  # selector de colormap
    levels = [panel._level.itemData(i) for i in range(panel._level.count())]
    assert "rows" in levels  # nivelado por filas disponible
    vm.set_data(_height_data())
    assert panel._image.image is not None


def test_image_analysis_panel_plots_profile(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = ImageViewModel()
    panel = ImageAnalysisPanel(vm)
    qtbot.addWidget(panel)
    assert not panel.errored
    vm.set_data(_height_data())
    vm.profile((5, 5), (50, 50))  # dispara profileChanged → grafica
    assert panel._plot.listDataItems()  # hay una curva de perfil
    vm.set_data(_potential_data())
    assert "KPFM" in panel._readout.text()  # readout muestra CPD para canal V


def test_profile_axis_uses_sensible_distance_units(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = ImageViewModel()
    panel = ImageAnalysisPanel(vm)
    qtbot.addWidget(panel)
    vm.set_data(_height_data())  # escaneo de 1 µm
    vm.profile((5, 5), (50, 50))  # traza un perfil → _on_profile fija la unidad
    unit = panel._plot.getAxis("bottom").labelUnits
    assert unit in ("nm", "µm")  # nunca 'km' para un escaneo de µm


def test_vm_tip_work_function_computes_phi_sample() -> None:
    vm = ImageViewModel()
    vm.set_data(_potential_data())
    assert vm.kpfm().work_function is None  # sin Φ de la punta
    vm.set_tip_work_function(4.5)
    assert vm.tip_work_function == 4.5
    assert vm.kpfm().work_function is not None  # Φ de la muestra calculada


def test_image_analysis_panel_work_function_control(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = ImageViewModel()
    panel = ImageAnalysisPanel(vm)
    qtbot.addWidget(panel)
    vm.set_data(_potential_data())
    panel._wf.setValue(4.5)  # el control empuja Φ punta al VM
    assert vm.tip_work_function == 4.5
    assert "Φ muestra" in panel._readout.text()  # el readout muestra la Φ de la muestra
