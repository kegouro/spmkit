"""Distinción imagen 2D vs canal espectral/1D (SPMChannel.is_spatial)."""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel


def _ch(data, dim1=None):
    meta = {"Dim1Name": dim1} if dim1 is not None else {}
    return SPMChannel(
        name="c", data=np.asarray(data), unit="m", x_range=1e-6, y_range=1e-6, metadata=meta
    )


def test_imagen_2d_es_espacial() -> None:
    assert _ch(np.zeros((32, 32)), dim1="Y-Axis").is_spatial  # nid imagen
    assert _ch(np.zeros((16, 16))).is_spatial  # sin Dim1Name (gwy) → 2D es imagen


def test_espectro_no_es_espacial() -> None:
    assert not _ch(np.zeros((1, 512)), dim1="SpecPoint").is_spatial  # 1 fila + no-Y
    assert not _ch(np.zeros((1, 512))).is_spatial  # línea 1×N sin metadata
    assert not _ch(np.zeros((512, 1))).is_spatial  # columna N×1
    assert not _ch(np.zeros((32, 32)), dim1="Frequency").is_spatial  # 2D pero eje no espacial
