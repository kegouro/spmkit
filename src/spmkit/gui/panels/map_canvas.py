"""Lienzo del mapa de propiedades (force-volume) — el reemplazo de los mapas de ANA/JPK.

Muestra una propiedad mecánica (módulo, adhesión, disipación…) como imagen 2D de la
grilla de curvas. Hacer clic en un píxel selecciona esa curva (linked brushing) y la
cruz sigue a la curva activa cuando cambia desde otro panel.
"""

from __future__ import annotations

import contextlib

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from spmkit.core.analysis.forcevolume import VolumeResult
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import PROPERTIES, ForceViewModel, MapViewModel


class MapCanvasPanel(Panel):
    """Panel central de la perspectiva de mapa: imagen de propiedad + cruz enlazada."""

    title = "Mapa de propiedades"

    def __init__(
        self, map_vm: MapViewModel, force_vm: ForceViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = map_vm
        self._force_vm = force_vm
        self._grid: tuple[int, int] = (0, 0)
        super().__init__(parent)
        map_vm.mapReady.connect(self._on_map_ready)
        map_vm.keyChanged.connect(self._on_key_changed)
        map_vm.computingChanged.connect(self._on_computing)
        force_vm.curveChanged.connect(self._move_target)

    def build(self) -> QWidget:
        import pyqtgraph as pg

        pg.setConfigOption("imageAxisOrder", "row-major")

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        bar = QHBoxLayout()
        self._selector = QComboBox()
        for key in self._vm.keys:
            self._selector.addItem(PROPERTIES.get(key, (key,))[0], key)
        self._selector.currentIndexChanged.connect(self._on_selector)
        self._compute_btn = QPushButton("Calcular mapa")
        self._compute_btn.setProperty("primary", "true")
        self._compute_btn.clicked.connect(lambda: self._vm.compute())
        self._status = QLabel("mapa sin calcular")
        self._status.setProperty("role", "muted")
        bar.addWidget(QLabel("Propiedad:"))
        bar.addWidget(self._selector)
        bar.addWidget(self._compute_btn)
        bar.addStretch(1)
        bar.addWidget(self._status)

        self._image = pg.ImageView()
        self._image.ui.roiBtn.hide()
        self._image.ui.menuBtn.hide()
        with contextlib.suppress(Exception):  # colormap opcional; el default sirve
            self._image.setColorMap(pg.colormap.get("inferno"))
        self._target = pg.TargetItem(movable=False, pen=pg.mkPen("#2DD4BF", width=1.5), size=14)
        self._target.setVisible(False)
        self._image.getView().addItem(self._target)
        self._image.getView().scene().sigMouseClicked.connect(self._on_click)

        lay.addLayout(bar)
        lay.addWidget(self._image, 1)
        return root

    # ---- reacciones ----
    def _on_selector(self, _idx: int) -> None:
        key = self._selector.currentData()
        if key:
            self._vm.set_key(key)

    def _on_key_changed(self, _key: str) -> None:
        self._redraw()

    def _on_computing(self, computing: bool) -> None:
        self._compute_btn.setEnabled(not computing)
        self._compute_btn.setText("Calculando…" if computing else "Calcular mapa")

    def _on_map_ready(self, result: VolumeResult | None) -> None:
        if result is None:
            self._image.clear()
            self._target.setVisible(False)
            self._status.setText("mapa sin calcular")
            return
        self._grid = result.grid_shape
        self._status.setText(f"{result.n_ok} ok · {result.n_failed} fallidas")
        self._redraw()
        self._move_target(self._force_vm.index)

    def _redraw(self) -> None:
        result = self._vm.result
        if result is None:
            return
        key = self._vm.key
        if key not in result.maps:
            return
        scale = PROPERTIES.get(key, (key, 1.0, ""))[1]
        self._image.setImage(np.asarray(result.maps[key]) * scale, autoRange=True)
        self._image.getView().autoRange(padding=0.02)
        # Refleja la propiedad activa en el selector sin re-disparar la señal.
        idx = self._selector.findData(key)
        if idx >= 0 and idx != self._selector.currentIndex():
            self._selector.blockSignals(True)
            self._selector.setCurrentIndex(idx)
            self._selector.blockSignals(False)

    # ---- linked brushing ----
    def _on_click(self, event: object) -> None:
        if self._vm.result is None:
            return
        if getattr(event, "button", lambda: None)() != Qt.MouseButton.LeftButton:
            return  # sólo clic izquierdo selecciona (el derecho es menú de contexto)
        view = self._image.getView()
        point = view.mapSceneToView(event.scenePos())  # type: ignore[attr-defined]
        rows, cols = self._grid
        col = int(np.clip(int(np.floor(point.x())), 0, cols - 1))
        row = int(np.clip(int(np.floor(point.y())), 0, rows - 1))
        self._vm.select(row * cols + col)

    def _move_target(self, index: int) -> None:
        rows, cols = self._grid
        if cols <= 0 or not (0 <= index < rows * cols):
            self._target.setVisible(False)
            return
        row, col = divmod(index, cols)
        self._target.setPos(col + 0.5, row + 0.5)
        self._target.setVisible(True)
