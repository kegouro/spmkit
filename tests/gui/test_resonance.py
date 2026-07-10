"""Tests de la sintonía térmica (ViewModel + panel): resonancia desde el hub de imagen."""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel, SPMData
from spmkit.gui.panels.resonance_canvas import ResonanceCanvasPanel
from spmkit.gui.viewmodels import ImageViewModel, ResonanceViewModel


def _thermal_data(f0: float = 60000.0, q: float = 200.0) -> SPMData:
    """SPMData de sintonía térmica sintético: un pico Lorentziano (SHO) que extract_thermal lee."""
    n = 4000
    f_min, f_max = 30000.0, 90000.0
    freq = np.linspace(f_min, f_max, n)
    r = freq / f0
    psd = 1.0 / np.sqrt((1.0 - r**2) ** 2 + (r / q) ** 2)  # amplitud SHO, pico en f0
    ch = SPMChannel(
        name="FFT",
        data=psd.reshape(1, -1),
        unit="m",
        x_range=1.0,
        y_range=1.0,
        group="FFT",
        metadata={"Dim0Min": f_min, "Dim0Range": f_max - f_min},
    )
    return SPMData(
        channels=(ch,),
        metadata={
            "info": {"Frequency:": "60 kHz", "Q Factor:": "200", "Spring Constant:": "0.4 N/m"}
        },
    )


def test_resonance_vm_finds_peak() -> None:
    image_vm = ImageViewModel()
    vm = ResonanceViewModel(image_vm)
    seen: list = []
    vm.resultChanged.connect(seen.append)
    image_vm.set_data(_thermal_data())
    assert vm.result is not None
    assert abs(vm.result.peak.f0 - 60000.0) < 200.0  # recupera f0
    assert vm.result.peak.q_factor > 50.0  # Q finito por FWHM
    assert abs(vm.result.reported_k - 0.4) < 1e-9  # k reportada parseada del info
    assert seen and seen[-1] is vm.result


def test_resonance_vm_range_recomputes() -> None:
    image_vm = ImageViewModel()
    vm = ResonanceViewModel(image_vm)
    image_vm.set_data(_thermal_data())
    vm.set_range(50000.0, 70000.0)  # acota alrededor del pico
    assert vm.range == (50000.0, 70000.0)
    assert vm.result is not None and abs(vm.result.peak.f0 - 60000.0) < 200.0


def test_resonance_vm_non_thermal_data_emits_none() -> None:
    image_vm = ImageViewModel()
    vm = ResonanceViewModel(image_vm)
    z = np.zeros((16, 16))
    image_vm.set_data(
        SPMData(channels=(SPMChannel(name="Z", data=z, unit="m", x_range=1e-6, y_range=1e-6),))
    )
    # Una topografía normal no rompe: da un pico degenerado o None, nunca una excepción.
    assert vm.result is None or vm.result.peak is not None


def test_resonance_panel_plots(qtbot) -> None:  # type: ignore[no-untyped-def]
    image_vm = ImageViewModel()
    vm = ResonanceViewModel(image_vm)
    panel = ResonanceCanvasPanel(vm)
    qtbot.addWidget(panel)
    assert not panel.errored
    image_vm.set_data(_thermal_data())
    assert "f₀" in panel._readout.text()
    assert panel._plot.listDataItems()  # espectro graficado
    assert panel._f0_line.isVisible()  # marcador de resonancia visible
