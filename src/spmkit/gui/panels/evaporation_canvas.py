"""Panel de evaporación — sensado de masa por desplazamiento de frecuencia.

Carga una carpeta de espectros de sintonía térmica y grafica la resonancia f(t) y la masa
añadida Δm(t) en el tiempo, con el ajuste de la ley d² en el readout. Reacciona a
:class:`EvaporationViewModel`. Equivalente visual del comando ``spmkit evaporation``.
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spmkit.gui.design import tokens
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels.evaporation_vm import EvaporationResult, EvaporationViewModel

_H = 1.0 / 3600.0  # s → h
_KHZ = 1e-3  # Hz → kHz
_NG = 1e12  # kg → ng
_UM = 1e6  # m → µm

_EMPTY = "<i>Sin serie (abre una carpeta de espectros de sintonía térmica .nid)</i>"


def _readout_html(result: EvaporationResult | None) -> str:
    if result is None:
        return _EMPTY
    s, d2 = result.series, result.d2
    parts = [
        f"<b>Δm₀ = {s.added_mass[0] * _NG:.3g} ng</b>",
        f"k = {s.spring_constant:.3g} N/m",
        f"f₀ desnuda = {s.bare_frequency * _KHZ:.4g} kHz",
        f"r₀ = {d2.r0 * _UM:.3g} µm",
    ]
    if np.isfinite(d2.tau):
        parts.append(f"τ = {d2.tau * _H:.3g} h")
    parts.append(f"R² = {d2.r_squared:.3f}")
    parts.append("difusión: " + ("sí" if d2.is_diffusion_limited else "no"))
    return "  ·  ".join(parts)


class EvaporationCanvasPanel(Panel):
    """Panel central de la perspectiva Evaporación: carpeta → f(t) y Δm(t) + ley d²."""

    title = "Evaporación"

    def __init__(self, vm: EvaporationViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.resultChanged.connect(self._on_result)
        self._on_result(vm.result)

    def build(self) -> QWidget:
        import pyqtgraph as pg

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(6, 6, 6, 6)

        self._readout = QLabel(_EMPTY)
        self._readout.setProperty("role", "readout")
        self._readout.setWordWrap(True)
        lay.addWidget(self._readout)

        bar = QHBoxLayout()
        self._open_btn = QPushButton("Abrir serie…")
        self._open_btn.setProperty("primary", "true")
        self._open_btn.setToolTip(
            "Carpeta con espectros de sintonía térmica (.nid), uno por instante"
        )
        self._open_btn.clicked.connect(self._choose_folder)
        bar.addWidget(self._open_btn)

        bar.addWidget(QLabel("x/L:"))
        self._pos = QDoubleSpinBox()
        self._pos.setRange(0.01, 1.0)
        self._pos.setDecimals(3)
        self._pos.setSingleStep(0.05)
        self._pos.setValue(1.0)
        self._pos.setToolTip("Posición de carga x/L (micrografía); k(x)=k(L)/(x/L)³")
        self._pos.valueChanged.connect(self._vm.set_position)
        bar.addWidget(self._pos)

        bar.addWidget(QLabel("k (N/m, 0=auto):"))
        self._k = QDoubleSpinBox()
        self._k.setRange(0.0, 1000.0)
        self._k.setDecimals(4)
        self._k.setSingleStep(0.1)
        self._k.setValue(0.0)
        self._k.setToolTip("Constante de resorte k(L); 0 = usa la del archivo (ruido térmico)")
        self._k.valueChanged.connect(self._vm.set_spring_constant)
        bar.addWidget(self._k)

        self._export_btn = QPushButton("Exportar CSV…")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_csv)
        bar.addWidget(self._export_btn)
        bar.addStretch(1)
        lay.addLayout(bar)

        self._plot_f = pg.PlotWidget()
        self._plot_f.setLabel("bottom", "Tiempo (h)")
        self._plot_f.setLabel("left", "f (kHz)")
        self._plot_f.showGrid(x=True, y=True, alpha=0.3)
        lay.addWidget(self._plot_f, 1)

        self._plot_m = pg.PlotWidget()
        self._plot_m.setLabel("bottom", "Tiempo (h)")
        self._plot_m.setLabel("left", "Δm (ng)")
        self._plot_m.showGrid(x=True, y=True, alpha=0.3)
        self._plot_m.setXLink(self._plot_f)
        lay.addWidget(self._plot_m, 1)
        return root

    # ---- acciones ----
    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta de espectros de sintonía")
        if folder:
            self._vm.load_folder(folder)

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar serie", "evaporacion.csv", "CSV (*.csv)"
        )
        if path:
            self._vm.export_csv(path)

    # ---- reacciones ----
    def _on_result(self, result: EvaporationResult | None) -> None:
        import pyqtgraph as pg

        self._plot_f.clear()
        self._plot_m.clear()
        self._readout.setText(_readout_html(result))
        self._export_btn.setEnabled(result is not None)
        if result is None:
            return
        s = result.series
        t_h = np.asarray(s.time) * _H
        self._plot_f.plot(
            t_h,
            np.asarray(s.frequency) * _KHZ,
            pen=pg.mkPen(tokens.TRACES["fit"], width=1.8),
            symbol="o",
            symbolSize=5,
            symbolBrush=tokens.TRACES["fit"],
        )
        self._plot_m.plot(
            t_h,
            np.asarray(s.added_mass) * _NG,
            pen=pg.mkPen(tokens.TRACES["contact"], width=1.8),
            symbol="o",
            symbolSize=5,
            symbolBrush=tokens.TRACES["contact"],
        )
