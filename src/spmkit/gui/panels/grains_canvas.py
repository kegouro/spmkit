"""Panel de granos — detección de partículas con overlay y estadística (perspectiva Granos).

Muestra la topografía nivelada con los granos detectados superpuestos en color, más
controles (tamaño mínimo, altura relativa) y estadística (conteo, diámetro medio,
cobertura, densidad). Reacciona a :class:`GrainsViewModel`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels.grains_vm import GrainsViewModel

# LUT categórica para el overlay: 12 colores estables (grano i → color i%12), α≈140.
_GRAIN_COLORS = np.array(
    [
        [230, 25, 75],
        [60, 180, 75],
        [255, 225, 25],
        [67, 99, 216],
        [245, 130, 49],
        [145, 30, 180],
        [66, 212, 244],
        [240, 50, 230],
        [191, 239, 69],
        [250, 190, 212],
        [70, 153, 144],
        [154, 99, 36],
    ],
    dtype=np.ubyte,
)


def _stats_line(result: Any) -> str:
    if result is None:
        return "— (ajusta parámetros y pulsa Detectar)"
    if result.n_grains == 0:
        return "0 granos"
    scale, unit = (1e9, "nm") if result.unit_length == "m" else (1.0, result.unit_length)
    return (
        f"{result.n_grains} granos · Ø {result.mean_diameter * scale:.3g} {unit} · "
        f"cobertura {result.coverage * 100:.1f}% · {result.density:.3g}/µm²"
    )


class GrainsCanvasPanel(Panel):
    """Panel central de la perspectiva Granos."""

    title = "Granos"

    def __init__(self, vm: GrainsViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.resultChanged.connect(self._on_result)

    def build(self) -> QWidget:
        import pyqtgraph as pg

        pg.setConfigOption("imageAxisOrder", "row-major")

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        bar = QHBoxLayout()
        self._min_size = QSpinBox()
        self._min_size.setRange(1, 100000)
        self._min_size.setValue(self._vm.min_size)
        self._min_size.valueChanged.connect(self._vm.set_min_size)
        self._rel = QDoubleSpinBox()
        self._rel.setRange(0.05, 1.0)
        self._rel.setSingleStep(0.05)
        self._rel.setValue(self._vm.relative_height)
        self._rel.valueChanged.connect(self._vm.set_relative_height)

        # Umbral automático (relativo) o absoluto en nm.
        self._auto = QCheckBox("Auto")
        self._auto.setChecked(True)
        self._auto.setToolTip(
            "Umbral automático (fracción de altura). Desmárcalo para uno absoluto."
        )
        self._auto.toggled.connect(self._on_auto_toggled)
        self._abs = QDoubleSpinBox()
        self._abs.setRange(0.0, 1_000_000.0)
        self._abs.setDecimals(2)
        self._abs.setSuffix(" nm")
        self._abs.setEnabled(False)
        self._abs.valueChanged.connect(self._push_threshold)

        detect = QPushButton("Detectar")
        detect.setProperty("primary", True)
        detect.clicked.connect(self._vm.detect)
        self._stats = QLabel("—")
        self._stats.setProperty("role", "readout")
        bar.addWidget(QLabel("Tamaño mín (px):"))
        bar.addWidget(self._min_size)
        bar.addWidget(QLabel("Altura rel.:"))
        bar.addWidget(self._rel)
        bar.addWidget(self._auto)
        bar.addWidget(QLabel("Umbral:"))
        bar.addWidget(self._abs)
        bar.addWidget(detect)
        bar.addStretch(1)
        bar.addWidget(self._stats)
        lay.addLayout(bar)

        self._view = pg.ImageView()
        self._view.ui.roiBtn.hide()
        self._view.ui.menuBtn.hide()
        self._overlay = pg.ImageItem()
        self._overlay.setZValue(10)  # sobre la topografía
        self._view.getView().addItem(self._overlay)
        lay.addWidget(self._view, 1)
        return root

    def _on_auto_toggled(self, auto: bool) -> None:
        self._abs.setEnabled(not auto)
        self._rel.setEnabled(auto)
        self._vm.set_threshold(None if auto else self._abs.value() * 1e-9)

    def _push_threshold(self, _value: float) -> None:
        if not self._auto.isChecked():
            self._vm.set_threshold(self._abs.value() * 1e-9)  # nm → m

    # ---- reacciones ----
    def _on_result(self, result: Any) -> None:
        import contextlib

        ch = self._vm.base_channel()
        if ch is not None:
            self._view.setImage(np.asarray(ch.data), autoRange=True)
            with contextlib.suppress(Exception):
                from spmkit.gui.design.pg_colormaps import pyqtgraph_cmap

                self._view.setColorMap(pyqtgraph_cmap("gold"))
            self._view.getView().autoRange(padding=0.02)
        self._draw_overlay(result)
        self._stats.setText(_stats_line(result))

    def _draw_overlay(self, result: Any) -> None:
        if result is None or result.n_grains == 0:
            self._overlay.clear()
            return
        labels = np.asarray(result.labels)
        rgba = np.zeros((*labels.shape, 4), dtype=np.ubyte)
        colored = labels > 0
        idx = (labels[colored] - 1) % len(_GRAIN_COLORS)
        rgba[colored, :3] = _GRAIN_COLORS[idx]
        rgba[colored, 3] = 140  # semitransparente sobre la topografía
        self._overlay.setImage(rgba)
