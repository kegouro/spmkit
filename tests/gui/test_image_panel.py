"""Tests del visor de imágenes (ViewModel + panel) con un .nid real si está."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spmkit.core.models import SPMChannel, SPMData
from spmkit.gui.panels.image_canvas import ImageCanvasPanel
from spmkit.gui.viewmodels import ImageViewModel

_SAMPLE = next(
    (p for p in (Path(__file__).resolve().parents[2] / "reference" / "sample_files").glob("*.nid")),
    None,
)


def _synthetic_data() -> SPMData:
    z = np.tile(np.linspace(0, 1e-8, 64), (64, 1)) + np.random.default_rng(0).normal(
        0, 1e-10, (64, 64)
    )
    return SPMData(
        channels=(SPMChannel(name="Z-Axis", data=z, unit="m", x_range=1e-6, y_range=1e-6),)
    )


def test_image_vm_levels_and_roughness() -> None:
    vm = ImageViewModel()
    vm.set_data(_synthetic_data())
    assert vm.names == ["Z-Axis"]
    assert vm.channel == "Z-Axis"
    ch = vm.current_channel()
    assert ch is not None and ch.data.shape == (64, 64)
    assert vm.roughness() is not None  # es un canal de altura


def test_image_panel_draws(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = ImageViewModel()
    panel = ImageCanvasPanel(vm)
    qtbot.addWidget(panel)
    assert not panel.errored
    vm.set_data(_synthetic_data())
    assert panel._image.image is not None
    assert panel._channel.count() == 1
    assert panel._rough.text() != "—"


@pytest.mark.skipif(_SAMPLE is None, reason="sin .nid de imagen de prueba (gitignored)")
def test_image_panel_opens_real_nid(qtbot) -> None:  # type: ignore[no-untyped-def]
    from spmkit.core.io import load as load_image

    vm = ImageViewModel()
    panel = ImageCanvasPanel(vm)
    qtbot.addWidget(panel)
    vm.set_data(load_image(_SAMPLE))
    assert panel._image.image is not None
    assert panel._channel.count() >= 1
