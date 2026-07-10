"""Tests de grains + espectral en Fathom (F3.2) — VMs sobre el hub de imagen + paneles."""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from spmkit.core.models import SPMChannel, SPMData
from spmkit.gui.panels.grains_canvas import GrainsCanvasPanel
from spmkit.gui.panels.spectral_canvas import SpectralCanvasPanel
from spmkit.gui.viewmodels import GrainsViewModel, ImageViewModel, SpectralViewModel

_HAS_SCIPY = importlib.util.find_spec("scipy") is not None


def _bumps() -> SPMData:
    z = np.zeros((32, 32), dtype=float)
    for r, c in [(6, 6), (6, 24), (24, 12)]:  # tres partículas cuadradas
        z[r - 2 : r + 2, c - 2 : c + 2] = 1e-8
    return SPMData(channels=(SPMChannel(name="Z", data=z, unit="m", x_range=1e-6, y_range=1e-6),))


def _rough_surface() -> SPMData:
    rng = np.random.default_rng(0)
    z = rng.normal(0, 1e-9, (48, 48))
    return SPMData(channels=(SPMChannel(name="Z", data=z, unit="m", x_range=1e-6, y_range=1e-6),))


def test_spectral_vm_computes_on_data() -> None:
    image_vm = ImageViewModel()
    vm = SpectralViewModel(image_vm)
    seen: list[object] = []
    vm.resultChanged.connect(seen.append)
    image_vm.set_data(_rough_surface())
    assert vm.result is not None
    assert np.isfinite(vm.result.fractal.fractal_dimension)
    assert vm.result.psd.q.size > 1
    assert seen and seen[-1] is vm.result


def test_spectral_panel_plots(qtbot) -> None:  # type: ignore[no-untyped-def]
    image_vm = ImageViewModel()
    vm = SpectralViewModel(image_vm)
    panel = SpectralCanvasPanel(vm)
    qtbot.addWidget(panel)
    assert not panel.errored
    image_vm.set_data(_rough_surface())
    assert panel._plot.listDataItems()  # PSD graficada
    assert "D =" in panel._readout.text()


def test_grains_vm_threshold_state() -> None:
    vm = GrainsViewModel(ImageViewModel())
    assert vm.threshold is None  # automático (relativo) por defecto
    vm.set_threshold(5e-9)
    assert vm.threshold == 5e-9
    vm.set_threshold(None)
    assert vm.threshold is None


def test_grains_panel_auto_toggle(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = GrainsViewModel(ImageViewModel())
    panel = GrainsCanvasPanel(vm)
    qtbot.addWidget(panel)
    assert not panel._abs.isEnabled()  # Auto → umbral absoluto deshabilitado
    panel._abs.setValue(12.0)  # nm
    panel._auto.setChecked(False)
    assert panel._abs.isEnabled() and not panel._rel.isEnabled()
    assert vm.threshold is not None and abs(vm.threshold - 12e-9) < 1e-15  # nm → m


@pytest.mark.skipif(not _HAS_SCIPY, reason="grains requiere scipy (extra 'grains')")
def test_grains_vm_detects() -> None:
    image_vm = ImageViewModel()
    image_vm.set_data(_bumps())
    image_vm.set_leveling("none")  # deja las partículas intactas
    vm = GrainsViewModel(image_vm)
    vm.set_min_size(1)
    seen: list[object] = []
    vm.resultChanged.connect(seen.append)
    vm.detect()
    assert vm.result is not None and vm.result.n_grains == 3
    assert seen[-1] is vm.result


@pytest.mark.skipif(not _HAS_SCIPY, reason="grains requiere scipy (extra 'grains')")
def test_grains_panel_overlay(qtbot) -> None:  # type: ignore[no-untyped-def]
    image_vm = ImageViewModel()
    image_vm.set_data(_bumps())
    image_vm.set_leveling("none")
    vm = GrainsViewModel(image_vm)
    vm.set_min_size(1)
    panel = GrainsCanvasPanel(vm)
    qtbot.addWidget(panel)
    vm.detect()
    assert "3 granos" in panel._stats.text()
    assert panel._overlay.image is not None  # overlay dibujado
