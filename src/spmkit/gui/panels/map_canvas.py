"""Lienzo del mapa de propiedades (force-volume) — el reemplazo de los mapas de ANA/JPK.

Muestra una propiedad mecánica (módulo, adhesión, disipación…) como imagen 2D de la
grilla de curvas. Hacer clic en un píxel selecciona esa curva (linked brushing) y la
cruz sigue a la curva activa cuando cambia desde otro panel.
"""

from __future__ import annotations

import contextlib

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from spmkit.core import compute
from spmkit.core.analysis.forcevolume import VolumeResult
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import PROPERTIES, ForceViewModel, MapViewModel

#: Motores de cálculo del mapa: valor interno → etiqueta.
_ENGINES = (
    ("fast_cpu", "CPU · rápido"),
    ("fast_gpu", "GPU · rápido"),
    ("pipeline", "CPU · pipeline"),
)

#: Paletas de color disponibles para el mapa (paridad con ANA/JPK).
_COLORMAPS = ("inferno", "viridis", "magma", "plasma", "gold", "gray")


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
        # Motor: rápido (vectorizado CPU/GPU) o pipeline. GPU sólo si hay CUDA.
        gpu_ok = "gpu" in compute.available_backends()
        self._engine = QComboBox()
        for value, label in _ENGINES:
            if value == "fast_gpu" and not gpu_ok:
                continue
            self._engine.addItem(label, value)
        self._compute_btn = QPushButton("Calcular mapa")
        self._compute_btn.setProperty("primary", "true")
        self._compute_btn.clicked.connect(lambda: self._vm.compute(self._engine.currentData()))
        self._info = QToolButton()
        self._info.setText("ⓘ")
        self._info.setToolTip("¿CPU o GPU? — diferencias")
        self._info.clicked.connect(self._show_engine_info)
        # Colormap (paridad con ANA/JPK: elegir la paleta del mapa).
        self._cmap = QComboBox()
        self._cmap.addItems(_COLORMAPS)
        self._cmap.currentTextChanged.connect(self._apply_colormap)
        self._status = QLabel("mapa sin calcular")
        self._status.setProperty("role", "muted")
        bar.addWidget(QLabel("Propiedad:"))
        bar.addWidget(self._selector)
        bar.addWidget(QLabel("Motor:"))
        bar.addWidget(self._engine)
        bar.addWidget(self._info)
        bar.addWidget(QLabel("Color:"))
        bar.addWidget(self._cmap)
        bar.addWidget(self._compute_btn)
        bar.addStretch(1)
        bar.addWidget(self._status)

        self._image = pg.ImageView()
        self._image.ui.roiBtn.hide()
        self._image.ui.menuBtn.hide()
        self._apply_colormap()
        self._target = pg.TargetItem(movable=False, pen=pg.mkPen("#2DD4BF", width=1.5), size=14)
        self._target.setVisible(False)
        self._image.getView().addItem(self._target)
        self._image.getView().scene().sigMouseClicked.connect(self._on_click)

        lay.addLayout(bar)
        lay.addWidget(self._image, 1)
        return root

    def _apply_colormap(self, name: str = "") -> None:
        """Aplica la paleta seleccionada al mapa (matplotlib o 'gold' del laboratorio)."""
        import pyqtgraph as pg

        name = name or self._cmap.currentText()
        cmap = None
        if name == "gold":
            from spmkit.core.viz import colormaps

            with contextlib.suppress(Exception):
                cmap = colormaps.pyqtgraph_cmap("gold")
        else:
            with contextlib.suppress(Exception):
                cmap = pg.colormap.get(name)
        if cmap is not None:
            self._image.setColorMap(cmap)

    def _show_engine_info(self) -> None:
        """Pop-up breve explicando la diferencia CPU vs GPU y el pipeline."""
        gpu_ok = "gpu" in compute.available_backends()
        gpu_line = compute.GPU_INFO if gpu_ok else (compute.GPU_INFO + "\n\n(No disponible aquí.)")
        box = QMessageBox(self)
        box.setWindowTitle("Motor de cálculo del mapa")
        box.setText(
            f"<b>CPU · rápido</b><br>{compute.CPU_INFO}<br><br>"
            f"<b>GPU · rápido</b><br>{gpu_line}<br><br>"
            "<b>CPU · pipeline</b><br>Ajuste por curva: más lento pero respeta suavizado, "
            "región de ajuste y calibración manual, y calcula todas las propiedades."
        )
        box.exec()

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
