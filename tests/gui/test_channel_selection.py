"""Selección de canal por posición: canales con nombre duplicado son alcanzables.

Los ``.nid`` traen canales con el mismo ``Dim2Name`` (Z-Axis forward+backward, FFT+Fit).
La GUI selecciona por índice, no por nombre, y desambigua la etiqueta con el frame/dirección.
"""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel, SPMData
from spmkit.gui.viewmodels import FigureViewModel, ImageViewModel, View3DViewModel
from spmkit.gui.viewmodels.image_vm import channel_labels


def _dup_data() -> SPMData:
    """Dos canales de igual nombre (``Z-Axis``), distinguibles por frame/dirección/valor."""
    a = SPMChannel(
        "Z-Axis", np.ones((8, 8)), "m", 1e-6, 1e-6, direction="forward", group="Scan forward"
    )
    b = SPMChannel(
        "Z-Axis", np.full((8, 8), 2.0), "m", 1e-6, 1e-6, direction="backward", group="Scan backward"
    )
    return SPMData(channels=(a, b))


def test_channel_labels_disambiguates() -> None:
    labels = channel_labels(_dup_data())
    assert labels[0] != labels[1]  # etiquetas únicas pese al nombre repetido
    assert labels[0].startswith("Z-Axis") and labels[1].startswith("Z-Axis")


def test_second_duplicate_channel_is_reachable() -> None:
    vm = ImageViewModel()
    vm.set_data(_dup_data())
    vm.set_channel_index(1)  # el SEGUNDO canal (backward), inalcanzable con selección por nombre
    assert vm.current_index == 1
    assert vm.raw_channel_at(vm.current_index).data.mean() == 2.0


def test_figure_and_view3d_follow_the_correct_channel() -> None:
    ivm = ImageViewModel()
    ivm.set_data(_dup_data())
    fvm = FigureViewModel(ivm)
    vvm = View3DViewModel(ivm)
    fvm.set_index(1)
    vvm.set_index(1)
    assert (
        fvm.current_channel().data.mean() == 2.0
    )  # figura sigue el canal correcto (no el 1er match)
    assert vvm.current_channel().data.mean() == 2.0  # 3D idem


def test_set_channel_by_name_still_works() -> None:
    vm = ImageViewModel()
    vm.set_data(_dup_data())
    vm.set_channel("Z-Axis")  # compat: primer match
    assert vm.current_index == 0
