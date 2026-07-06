"""Panel espectral — PSD radial + dimensión fractal + correlación (perspectiva Espectral).

Grafica la PSD radialmente promediada en ejes log-log y muestra el exponente de Hurst,
la dimensión fractal, la pendiente β y la longitud de correlación. Reacciona a
:class:`SpectralViewModel` (recalcula al cambiar de canal).
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels.spectral_vm import SpectralResult, SpectralViewModel


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

    def build(self) -> QWidget:
        import pyqtgraph as pg

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(6, 6, 6, 6)

        self._readout = QLabel("<i>Sin datos (carga una imagen)</i>")
        self._readout.setProperty("role", "readout")
        self._readout.setWordWrap(True)
        lay.addWidget(self._readout)

        self._plot = pg.PlotWidget()
        self._plot.setLogMode(x=True, y=True)  # PSD en ley de potencia → recta en log-log
        self._plot.setLabel("bottom", "q (1/m)")
        self._plot.setLabel("left", "PSD (m⁴)")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        lay.addWidget(self._plot, 1)
        return root

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
