"""Panel espectral — PSD radial + dimensión fractal + correlación (perspectiva Espectral).

Grafica la PSD radialmente promediada en ejes log-log y muestra el exponente de Hurst,
la dimensión fractal, la pendiente β y la longitud de correlación. Reacciona a
:class:`SpectralViewModel` (recalcula al cambiar de canal).
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels.spectral_vm import SpectralResult, SpectralViewModel

_INV_UM = 1e6  # 1/m → 1/µm (unidad amigable para los controles de q)


def _readout_html(result: SpectralResult | None) -> str:
    if result is None:
        return "<i>Sin datos (carga una imagen)</i>"
    f = result.fractal
    corr_nm = result.correlation_length * 1e9
    return "  ·  ".join(
        [
            f"<b>D = {f.fractal_dimension:.3f}</b>",
            f"Hurst H = {f.hurst:.3f}",
            f"β = {f.psd_slope:.3f}",
            f"R² = {f.r_squared:.3f}",
            f"L<sub>corr</sub> = {corr_nm:.3g} nm",
        ]
    )


class SpectralCanvasPanel(Panel):
    """Panel central de la perspectiva Espectral."""

    title = "Espectral"

    def __init__(self, vm: SpectralViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.resultChanged.connect(self._on_result)
        self._on_result(vm.result)  # hidrata el estado actual (si ya hay datos cargados)

    def refresh(self) -> None:
        """Re-hidrata al activarse la perspectiva (el shell llama refresh_safe)."""
        self._on_result(self._vm.result)

    def build(self) -> QWidget:
        import pyqtgraph as pg

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(6, 6, 6, 6)

        self._readout = QLabel("<i>Sin datos (carga una imagen)</i>")
        self._readout.setProperty("role", "readout")
        self._readout.setWordWrap(True)
        lay.addWidget(self._readout)

        # Rango de ajuste fractal (q en 1/µm; 0 = automático).
        qrow = QHBoxLayout()
        qrow.addWidget(QLabel("Ajuste fractal — q min (1/µm):"))
        self._qmin = self._q_spin()
        qrow.addWidget(self._qmin)
        qrow.addWidget(QLabel("q max (1/µm):"))
        self._qmax = self._q_spin()
        qrow.addWidget(self._qmax)
        qrow.addStretch(1)
        lay.addLayout(qrow)

        self._plot = pg.PlotWidget()
        self._plot.setLogMode(x=True, y=True)  # PSD en ley de potencia → recta en log-log
        self._plot.setLabel("bottom", "q (1/m)")
        self._plot.setLabel("left", "PSD (m⁴)")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        lay.addWidget(self._plot, 1)
        return root

    def _q_spin(self) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(0.0, 100000.0)
        box.setDecimals(2)
        box.setToolTip("Frecuencia del ajuste fractal en 1/µm (0 = automático)")
        box.valueChanged.connect(self._push_q_range)
        return box

    def _push_q_range(self, _value: float = 0.0) -> None:
        qmin = (self._qmin.value() * _INV_UM) or None
        qmax = (self._qmax.value() * _INV_UM) or None
        self._vm.set_q_range(qmin, qmax)

    def _on_result(self, result: SpectralResult | None) -> None:
        import pyqtgraph as pg

        self._plot.clear()
        self._readout.setText(_readout_html(result))
        if result is None:
            return
        q = np.asarray(result.psd.q)
        psd = np.asarray(result.psd.psd)
        mask = (q > 0) & (psd > 0)  # log-log: descarta el bin DC y ceros
        if mask.any():
            self._plot.plot(q[mask], psd[mask], pen=pg.mkPen("#4ea1ff", width=2))
