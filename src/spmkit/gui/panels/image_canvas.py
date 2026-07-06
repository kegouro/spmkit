"""Visor de imágenes SPM — canal + nivelado + colormap + perfil, perspectiva Imagen.

Paridad de visor: elegir canal, nivelar (plano/polinomio/filas), colormap, y **trazar un
perfil de línea** arrastrando un ROI sobre la imagen (el :class:`ProfilePanel` lo grafica).
Usa el colormap "gold" estilo NanoSurf y el orden row-major de pyqtgraph (sin transponer).
"""

from __future__ import annotations

import contextlib

import numpy as np
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from spmkit.core.analysis.roughness import RoughnessResult
from spmkit.core.models import SPMChannel
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import ImageViewModel

_LEVELING = (
    ("plane", "Plano"),
    ("poly", "Polinomio"),
    ("rows", "Filas"),
    ("none", "Sin nivelar"),
)
_COLORMAPS = ("gold", "batlow", "viridis", "inferno", "afmhot", "gray")


def _roughness_line(result: RoughnessResult | None) -> str:
    if result is None:
        return "—"
    scale, unit = (1e9, "nm") if result.unit == "m" else (1.0, result.unit)
    return (
        f"Sa {result.Sa * scale:.3g} · Sq {result.Sq * scale:.3g} · "
        f"Sz {result.Sz * scale:.3g} {unit}"
    )


class ImageCanvasPanel(Panel):
    """Panel central de la perspectiva Imagen: canal + nivelado + colormap + perfil."""

    title = "Imagen"

    def __init__(self, vm: ImageViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.dataChanged.connect(self._on_data)
        vm.channelChanged.connect(self._on_channel)

    def build(self) -> QWidget:
        import pyqtgraph as pg

        pg.setConfigOption("imageAxisOrder", "row-major")

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
        self._cmap = QComboBox()
        self._cmap.addItems(_COLORMAPS)
        self._cmap.currentTextChanged.connect(self._apply_colormap)
        self._rough = QLabel("—")
        self._rough.setProperty("role", "readout")
        bar.addWidget(QLabel("Canal:"))
        bar.addWidget(self._channel)
        bar.addWidget(QLabel("Nivelado:"))
        bar.addWidget(self._level)
        bar.addWidget(QLabel("Colormap:"))
        bar.addWidget(self._cmap)
        bar.addStretch(1)
        bar.addWidget(self._rough)
        lay.addLayout(bar)

        self._image = pg.ImageView()
        self._image.ui.roiBtn.hide()
        self._image.ui.menuBtn.hide()
        self._apply_colormap()
        # ROI de perfil de línea (arrastra los extremos → ProfilePanel lo grafica).
        self._roi = pg.LineSegmentROI([[10, 10], [40, 40]], pen=pg.mkPen("#4ea1ff", width=2))
        self._roi.sigRegionChanged.connect(self._update_profile)
        self._image.addItem(self._roi)
        lay.addWidget(self._image, 1)
        return root

    # ---- colormap (concern de vista, como en map_canvas) ----
    def _apply_colormap(self, name: str = "") -> None:
        from spmkit.gui.design.pg_colormaps import pyqtgraph_cmap

        name = name or self._cmap.currentText() or "gold"
        with contextlib.suppress(Exception):
            self._image.setColorMap(pyqtgraph_cmap(name))

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
            self._update_profile()  # re-traza el perfil sobre el canal nuevo
        self._rough.setText(_roughness_line(self._vm.roughness()))

    def _draw(self, channel: SPMChannel) -> None:
        self._image.setImage(np.asarray(channel.data), autoRange=True)
        self._image.getView().autoRange(padding=0.02)

    def _update_profile(self) -> None:
        """Mapea el ROI a coordenadas de píxel y pide el perfil al VM."""
        handles = self._roi.getSceneHandlePositions()
        item = self._image.getImageItem()
        pts = [item.mapFromScene(h[1]) for h in handles]
        if len(pts) < 2:
            return
        self._vm.profile((pts[0].x(), pts[0].y()), (pts[1].x(), pts[1].y()))
