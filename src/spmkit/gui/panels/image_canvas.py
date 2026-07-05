"""Visor de imágenes SPM — canal + nivelado + rugosidad, en la perspectiva Imagen.

Básico a propósito (el norte del rediseño son las curvas de fuerza): abrir una imagen,
elegir canal, nivelar y ver la rugosidad. Usa el colormap "gold" estilo NanoSurf y el
orden row-major de pyqtgraph (sin transponer), como marca la guía del repo.
"""

from __future__ import annotations

import contextlib

import numpy as np
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from spmkit.core.analysis.roughness import RoughnessResult
from spmkit.core.models import SPMChannel
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import ImageViewModel

_LEVELING = (("plane", "Plano"), ("poly", "Polinomio"), ("none", "Sin nivelar"))


def _roughness_line(result: RoughnessResult | None) -> str:
    if result is None:
        return "—"
    scale, unit = (1e9, "nm") if result.unit == "m" else (1.0, result.unit)
    return (
        f"Sa {result.Sa * scale:.3g} · Sq {result.Sq * scale:.3g} · "
        f"Sz {result.Sz * scale:.3g} {unit}"
    )


class ImageCanvasPanel(Panel):
    """Panel central de la perspectiva Imagen: canal + nivelado + rugosidad."""

    title = "Imagen"

    def __init__(self, vm: ImageViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.dataChanged.connect(self._on_data)
        vm.channelChanged.connect(self._on_channel)

    def build(self) -> QWidget:
        import pyqtgraph as pg

        pg.setConfigOption("imageAxisOrder", "row-major")
        from spmkit.core.viz import colormaps

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        bar = QHBoxLayout()
        self._channel = QComboBox()
        self._channel.currentTextChanged.connect(self._vm.set_channel)
        self._level = QComboBox()
        for value, label in _LEVELING:
            self._level.addItem(label, value)
        self._level.currentIndexChanged.connect(
            lambda _i: self._vm.set_leveling(self._level.currentData())
        )
        self._rough = QLabel("—")
        self._rough.setProperty("role", "readout")
        bar.addWidget(QLabel("Canal:"))
        bar.addWidget(self._channel)
        bar.addWidget(QLabel("Nivelado:"))
        bar.addWidget(self._level)
        bar.addStretch(1)
        bar.addWidget(self._rough)
        lay.addLayout(bar)

        self._image = pg.ImageView()
        self._image.ui.roiBtn.hide()
        self._image.ui.menuBtn.hide()
        with contextlib.suppress(Exception):
            self._image.setColorMap(colormaps.pyqtgraph_cmap("gold"))
        lay.addWidget(self._image, 1)
        return root

    # ---- reacciones ----
    def _on_data(self, names: list) -> None:
        self._channel.blockSignals(True)
        self._channel.clear()
        self._channel.addItems([str(n) for n in names])
        self._channel.blockSignals(False)

    def _on_channel(self, name: str) -> None:
        if name and name != self._channel.currentText():
            self._channel.blockSignals(True)
            self._channel.setCurrentText(name)
            self._channel.blockSignals(False)
        ch = self._vm.current_channel()
        if ch is not None:
            self._draw(ch)
        self._rough.setText(_roughness_line(self._vm.roughness()))

    def _draw(self, channel: SPMChannel) -> None:
        self._image.setImage(np.asarray(channel.data), autoRange=True)
        self._image.getView().autoRange(padding=0.02)
