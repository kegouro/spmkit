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


def test_image_vm_poly_order_and_row_stat_recompute() -> None:
    vm = ImageViewModel()
    vm.set_data(_synthetic_data())
    vm.set_leveling("poly")
    seen: list = []
    vm.channelChanged.connect(seen.append)
    vm.set_poly_order(4)
    assert vm.poly_order == 4 and seen  # re-render con el grado nuevo
    vm.set_leveling("rows")
    vm.set_row_stat("mean")
    assert vm.row_stat == "mean"
    assert vm.current_channel() is not None  # el alineado por filas corre con el estadístico


def test_image_panel_level_controls_visibility(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = ImageViewModel()
    panel = ImageCanvasPanel(vm)
    qtbot.addWidget(panel)
    vm.set_data(_synthetic_data())
    panel._level.setCurrentIndex(panel._level.findData("poly"))
    assert not panel._order.isHidden() and panel._rowstat.isHidden()
    panel._order.setValue(3)
    assert vm.poly_order == 3  # el spin edita el VM
    panel._level.setCurrentIndex(panel._level.findData("rows"))
    assert not panel._rowstat.isHidden() and panel._order.isHidden()


def test_length_scale_picks_sensible_units() -> None:
    from spmkit.gui.panels.image_analysis import _length_scale

    assert _length_scale(5e-7)[1] == "nm"  # 500 nm
    assert _length_scale(1e-5)[1] == "µm"  # 10 µm
    assert _length_scale(2e-3)[1] == "mm"  # 2 mm
    assert _length_scale(50.0)[1] == "m"  # nunca 'km' (auto-prefijo SI desactivado)


def test_image_canvas_hydrates_already_loaded_data(qtbot) -> None:  # type: ignore[no-untyped-def]
    # Persistencia: construir el panel DESPUÉS de cargar datos no los pierde (bug "olvida al
    # cambiar de pestaña" — los paneles hidratan el estado actual del VM).
    vm = ImageViewModel()
    vm.set_data(_synthetic_data())
    panel = ImageCanvasPanel(vm)
    qtbot.addWidget(panel)
    assert panel._channel.count() == 1  # hidrató el canal ya cargado
    assert panel._image.image is not None  # y lo dibujó
    assert panel._rough.text() != "—"


def test_fit_image_view_bounds_pan(qtbot) -> None:  # type: ignore[no-untyped-def]
    import pyqtgraph as pg

    from spmkit.gui.panels._viewport import fit_image_view

    vb = pg.ViewBox()
    fit_image_view(vb, np.zeros((10, 20)))  # rows=10, cols=20
    xlim = vb.state["limits"]["xLimits"]
    ylim = vb.state["limits"]["yLimits"]
    assert xlim[0] <= 0 and xlim[1] >= 20  # acota el pan al extent en X (columnas)
    assert ylim[0] <= 0 and ylim[1] >= 10  # y en Y (filas) → sin desplazamiento infinito


def test_image_canvas_refresh_and_center(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = ImageViewModel()
    panel = ImageCanvasPanel(vm)
    qtbot.addWidget(panel)
    vm.set_data(_synthetic_data())
    panel.refresh()  # reencuadra al activar la perspectiva (shell → refresh_safe)
    panel._center_view()  # botón «Centrar»
    assert not panel.errored


@pytest.mark.skipif(_SAMPLE is None, reason="sin .nid de imagen de prueba (gitignored)")
def test_image_panel_opens_real_nid(qtbot) -> None:  # type: ignore[no-untyped-def]
    from spmkit.core.io import load as load_image

    vm = ImageViewModel()
    panel = ImageCanvasPanel(vm)
    qtbot.addWidget(panel)
    vm.set_data(load_image(_SAMPLE))
    assert panel._image.image is not None
    assert panel._channel.count() >= 1
