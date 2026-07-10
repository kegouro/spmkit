"""Panel de sintonía térmica — espectro de resonancia + f0/Q (perspectiva Sintonía térmica).

Grafica la densidad espectral vs frecuencia, marca la resonancia detectada en oro de marca y
muestra f0, Q y la constante de resorte reportada. Un rango de frecuencia (kHz) acota el pico.
Reacciona a :class:`ResonanceViewModel`.
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spmkit.gui.design import tokens
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels.resonance_vm import ResonanceResult, ResonanceViewModel

_KHZ = 1e-3  # Hz → kHz


def _readout_html(result: ResonanceResult | None) -> str:
    if result is None:
        return "<i>Sin espectro (carga un .nid de sintonía térmica)</i>"
    p = result.peak
    parts = [f"<b>f₀ = {p.f0 * _KHZ:.4g} kHz</b>", f"Q = {p.q_factor:.4g}"]
    if np.isfinite(result.reported_f0):
        parts.append(f"f₀ instrumento = {result.reported_f0 * _KHZ:.4g} kHz")
    if np.isfinite(result.reported_k):
        parts.append(f"k = {result.reported_k:.3g} N/m")
    return "  ·  ".join(parts)


class ResonanceCanvasPanel(Panel):
    """Panel central de la perspectiva Sintonía térmica."""

    title = "Sintonía térmica"

    def __init__(self, vm: ResonanceViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.resultChanged.connect(self._on_result)
        self._on_result(vm.result)

    def build(self) -> QWidget:
        import pyqtgraph as pg

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(6, 6, 6, 6)

        self._readout = QLabel("<i>Sin espectro (carga un .nid de sintonía térmica)</i>")
        self._readout.setProperty("role", "readout")
        self._readout.setWordWrap(True)
        lay.addWidget(self._readout)

        # Rango de frecuencia del pico (kHz; 0 = todo el espectro).
        frow = QHBoxLayout()
        frow.addWidget(QLabel("Rango — f min (kHz):"))
        self._fmin = self._f_spin()
        frow.addWidget(self._fmin)
        frow.addWidget(QLabel("f max (kHz):"))
        self._fmax = self._f_spin()
        frow.addWidget(self._fmax)
        frow.addStretch(1)
        lay.addLayout(frow)

        # Constante de resorte por ruido térmico (equipartición) sobre el rango activo.
        krow = QHBoxLayout()
        krow.addWidget(QLabel("Temp (°C):"))
        self._temp = QDoubleSpinBox()
        self._temp.setRange(-50.0, 200.0)
        self._temp.setDecimals(1)
        self._temp.setValue(20.0)
        krow.addWidget(self._temp)
        krow.addWidget(QLabel("χ:"))
        self._chi = QDoubleSpinBox()
        self._chi.setRange(0.1, 1.0)
        self._chi.setDecimals(3)
        self._chi.setSingleStep(0.01)
        self._chi.setValue(0.817)  # Butt & Jaschke, 1er modo, palanca óptica
        self._chi.setToolTip("Factor de forma de modo (0.817 para el 1er modo, óptica)")
        krow.addWidget(self._chi)
        calc_k = QPushButton("Calcular k (térmico)")
        calc_k.clicked.connect(self._calc_k)
        krow.addWidget(calc_k)
        self._k_readout = QLabel("")
        self._k_readout.setProperty("role", "readout")
        krow.addWidget(self._k_readout)
        krow.addStretch(1)
        lay.addLayout(krow)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "Frecuencia", units="Hz")
        self._plot.setLabel("left", "PSD", units="m/√Hz")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._f0_line = pg.InfiniteLine(angle=90, pen=pg.mkPen(tokens.TRACES["contact"], width=1.5))
        self._plot.addItem(self._f0_line)
        self._f0_line.hide()
        lay.addWidget(self._plot, 1)
        return root

    def _f_spin(self) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(0.0, 100000.0)
        box.setDecimals(2)
        box.setToolTip("Frecuencia en kHz (0 = sin límite)")
        box.valueChanged.connect(self._push_range)
        return box

    def _push_range(self, _value: float = 0.0) -> None:
        fmin = (self._fmin.value() / _KHZ) or None
        fmax = (self._fmax.value() / _KHZ) or None
        self._vm.set_range(fmin, fmax)

    def _calc_k(self) -> None:
        k = self._vm.spring_constant_thermal(self._temp.value(), self._chi.value())
        self._k_readout.setText(f"k = {k:.3g} N/m" if k is not None else "—")

    def _on_result(self, result: ResonanceResult | None) -> None:
        import pyqtgraph as pg

        self._plot.clear()
        self._plot.addItem(self._f0_line)
        self._readout.setText(_readout_html(result))
        if result is None:
            self._f0_line.hide()
            return
        self._plot.plot(
            np.asarray(result.frequency),
            np.asarray(result.psd),
            pen=pg.mkPen(tokens.TRACES["fit"], width=1.6),
        )
        self._f0_line.setValue(result.peak.f0)
        self._f0_line.show()
